"""Real capture in a new, private Dummy Audio REAPER process and synthetic library.

No HTTP ports, live project/profile, device selection or installed actions are used.
Only the process created here is closed. Artifacts and recordings are retained.
"""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
import wave

ROOT=Path(__file__).resolve().parent.parent


def verify_browser(result, folder):
    """Replay real native publications through the shipped browser wire handlers."""
    from playwright.sync_api import sync_playwright
    from test_browser import EDGE
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=str(EDGE),headless=True)
        page=browser.new_page(viewport={'width':1024,'height':768})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        def route(request):
            name=request.request.url.rsplit('/',1)[-1]
            if name=='main.js':request.fulfill(body='function wwr_req(){};function wwr_req_recur(){};function wwr_start(){}',content_type='text/javascript')
            elif name in ('ReaSet.html','Sortable.min.js'):request.fulfill(path=str(ROOT/name))
            else:request.fulfill(body='')
        page.route('**/*',route)
        page.goto('http://isolated.test/ReaSet.html')
        page.evaluate("document.getElementById('recording-panel').classList.add('open')")
        for generation,row in enumerate(result['snapshots'],1):
            page.evaluate('''v=>{
              const [gen,row]=v;g_stableId=row.state.project;
              recHandleExtState(['EXTSTATE','ReaSetRec','heartbeat',String(gen)]);
              recHandleExtState(['EXTSTATE','ReaSetRec','meta',gen+':1:0']);
              recHandleExtState(['EXTSTATE','ReaSetRec','d0_0',gen+':'+JSON.stringify(row.state)]);
              clHandleExtState(['EXTSTATE','ReaSetCL','heartbeat',String(gen)]);
              clHandleExtState(['EXTSTATE','ReaSetCL','meta',gen+':1']);
              clHandleExtState(['EXTSTATE','ReaSetCL','d0',gen+':'+JSON.stringify(row.chart)]);
              wwr_onreply('TRANSPORT\\t'+row.transport+'\\t'+row.position+'\\t0\\t0\\n');
            }''',[generation,row])
            if row['name'] in ('countin','recording','paused'):
                assert page.locator('#chords-panel').is_visible(),row['name']
                assert not page.locator('#recording-panel').is_visible(),row['name']
                expected=120+max(0,row['position']-row['state']['capture']['origin'])
                assert abs(page.evaluate('chartSongPosition()')-expected)<.001,row['name']
                page.screenshot(path=str(folder/(row['name']+'.png')))
            if row['name']=='review':
                assert page.get_by_role('button',name='Discard take',exact=True).is_visible()
                page.screenshot(path=str(folder/'review.png'))
        browser.close()
        assert not errors,errors


def main():
    executable=Path('C:/Program Files/REAPER (x64)/reaper.exe')
    sws=Path(os.environ['APPDATA'])/'REAPER/UserPlugins/reaper_sws-x64.dll'
    assert executable.is_file() and sws.is_file(),'REAPER and SWS required'
    folder=Path(tempfile.mkdtemp(prefix='reaset-playalong-')).resolve()
    resource=folder/'resource';(resource/'UserPlugins').mkdir(parents=True)
    # Copy the extension binary only, never the live REAPER configuration.
    shutil.copy2(sws,resource/'UserPlugins'/sws.name)
    shutil.copytree(ROOT/'Requirements',folder/'code/Requirements')
    ini=resource/'reaper.ini'
    ini.write_text('[REAPER]\nwnd_state=2\nnosplash=1\nloadlastproj=0\n'
                   '[audioconfig]\nmode=4\ndummy_srate=48000\ndummy_blocksize=512\n',encoding='utf-8')
    pcm=[0]*(22050*9)
    beats=[.05+i*.25 for i in range(36)]
    for beat in beats:pcm[round(beat*22050)]=16000
    with wave.open(str(folder/'click.wav'),'wb') as out:
        out.setparams((1,2,22050,0,'NONE','not compressed'))
        out.writeframes(struct.pack('<'+'h'*len(pcm),*pcm))
    (folder/'click-review.json').write_text(json.dumps({'beats':beats}),encoding='utf-8')
    script=folder/'worker.lua'
    script.write_text('local folder='+json.dumps(folder.as_posix())+'\n'+r'''
local J=dofile(folder..'/code/Requirements/ReaSet_JSON.lua')
local core,M,stage,at,key,savedFirst,pausedPos=nil,nil,0,0,nil,nil,nil
local result={snapshots={},checks={}}
local started=reaper.time_precise()
local function chart()
 local meta=reaper.GetExtState('ReaSetCL','meta');local gen,n=meta:match('^(%d+):(%d+)$')
 if not gen then return nil end
 local raw=''
 for i=0,tonumber(n)-1 do
  local v=reaper.GetExtState('ReaSetCL','d'..i)
  assert(v:match('^(%d+):')==gen,'Mixed chart generation')
  raw=raw..v:match('^%d+:(.*)$')
 end
 return J.decode(raw)
end
local function snapshot(name)
 result.snapshots[#result.snapshots+1]={name=name,state=core:state(),chart=chart(),transport=reaper.GetPlayState(),position=reaper.GetPlayState()==0 and reaper.GetCursorPosition()or reaper.GetPlayPosition()}
end
local function command(op,args)
 local c=args or {};c.op=op;c.project=core.id;c.revision=core.revision;core:command(c)
end
local function check(value,message)assert(value,message);result.checks[#result.checks+1]=message end
local function finish(ok,why)
 if core then
  pcall(function()if core.db.active then command('stop')end;core:park();core:release_device()end)
 end
 result.ok=ok;result.error=not ok and tostring(why)or nil
 local f=assert(io.open(folder..'/result.json','wb'));f:write(J.encode(result));f:close()
end
local function run()
 assert(reaper.time_precise()-started<55,'Private capture timed out')
 if stage==0 then
  local resource=reaper.GetResourcePath():gsub('\\','/')
  assert(resource:lower()==(folder..'/resource'):lower(),'Private resource guard failed')
  local ok,device=reaper.GetAudioDeviceInfo('MODE')
  assert(ok and device=='Dummy Audio','Dummy Audio guard failed')
  local _,path=reaper.EnumProjects(-1,'')
  assert(path=='' and reaper.CountTracks(0)==0 and reaper.GetPlayState()==0 and not reaper.EnumProjects(1,''),'Expected private empty project')
  assert(reaper.SNM_GetIntConfigVar,'Private SWS did not load')
  result.device=device;result.resource=resource;result.version=reaper.GetAppVersion()
  result.inputs=reaper.GetNumAudioInputs()
  -- Dummy Audio has no physical inputs. Exercise real native output capture;
  -- substitute only availability, never a hardware device or capture result.
  reaper.GetNumAudioInputs=function()return 2 end
  reaper.SetProjExtState(0,'ReaSet','projectId','isolated-playalong')
  reaper.AddProjectMarker2(0,true,120,129,'Synthetic song',7,0)
  reaper.InsertTrackAtIndex(0,false);local tr=reaper.GetTrack(0,0)
  reaper.GetSetMediaTrackInfo_String(tr,'P_NAME','[JR:CLICK] Synthetic click',true)
  reaper.SetMediaTrackInfo_Value(tr,'B_MAINSEND',0)
  local it=reaper.AddMediaItemToTrack(tr);local tk=reaper.AddTakeToMediaItem(it)
  reaper.SetMediaItemTake_Source(tk,assert(reaper.PCM_Source_CreateFromFile(folder..'/click.wav')))
  reaper.SetMediaItemInfo_Value(it,'D_POSITION',120);reaper.SetMediaItemInfo_Value(it,'D_LENGTH',9)
  local sections={}
  for i,label in ipairs({'Intro','Verse','Chorus'})do sections[i]={id='s'..i,label=label,start=(i-1)*3,['end']=i*3,rows={{id='r'..i,text=label..' synthetic words for playing together',anchors={{offset=0,symbol='C'}}}}}end
  reaper.SetProjExtState(0,'ReaSetSong','song:7:document',J.encode({schema=3,revision='synthetic',sections=sections,duration=9}))
  reaper.SetProjExtState(0,'ReaSetTK','bpm:Synthetic song','80')
  reaper.SetEditCurPos(120,false,false)
  reaper.Main_SaveProjectEx(0,folder..'/library.RPP',8)
  M=dofile(folder..'/code/Requirements/ReaSet_RecordingCore.lua');J=M.J;core=M.new();core:setup()
  local arm=core.arm
  core.arm=function(self,take)
   local count=arm(self,take)
   for _,dest in pairs(M.tracks())do reaper.SetMediaTrackInfo_Value(dest,'I_RECMODE',1)end
   return count
  end
  local start_native=core.start_native
  core.start_native=function(self)
   for i=0,reaper.CountTracks(0)-1 do
    local track=reaper.GetTrack(0,i)
    for n=reaper.GetTrackNumSends(track,1)-1,0,-1 do reaper.RemoveTrackSend(track,1,n)end
    reaper.SetMediaTrackInfo_Value(track,'B_MAINSEND',0)
   end
   return start_native(self)
  end
  for _,c in ipairs(core.db.inputs)do c.selected=c.id=='1' end
  core:save(false);key=M.P.songs()[1].key
  local id=reaper.AddRemoveReaScript(true,0,folder..'/code/Requirements/ReaSet_ChordsLyrics.lua',true)
  assert(id~=0);reaper.Main_OnCommand(id,0)
  command('ready');stage=1
 else
  core:tick()
  local state=core:state()
  reaper.SetExtState('ReaSetRec','lock',core.mode~='idle' and core.id or '',false)
  reaper.SetExtState('ReaSetRec','chart',state.capture and J.encode(state.capture)or'',false)
  if stage==1 and core.deviceState=='ready' and chart()then
   command('song',{song=key});snapshot('prepared');command('record',{song=key});stage=2
  elseif stage==2 then
   local c=chart()
   if c and c.capture and c.capture~=J.null then
    check(c.song.id==7 and c.capture.origin==state.capture.origin,'Loaded chart follows confirmed capture coordinates')
    check(core.mode=='countin' and math.abs(state.capture.leadin-2)<.0001,'Count-in matches installed click, not imported 80 BPM')
    snapshot('countin');stage=3
   end
  elseif stage==3 and core.mode=='recording' and state.elapsed>1 then
   snapshot('recording');command('pause');pausedPos=reaper.GetPlayPosition();at=reaper.time_precise();stage=4
  elseif stage==4 and reaper.time_precise()-at>.3 then
   check(reaper.GetPlayState()==6 and math.abs(reaper.GetPlayPosition()-pausedPos)<.05,'Native pause retains recording and chart position')
   snapshot('paused');command('pause');stage=5
  elseif stage==5 and core.mode=='review' then
   local s,t=M.mix_take(core);check(#t.items==1 and t.duration>=8.9,'Automatic song end saves a full take')
   savedFirst=t.id;snapshot('review');stage=6
  elseif stage==6 then
   local s,t=M.mix_take(core)
   command('prepareTake',{kind='new',session=s.id,take=t.id});command('cancelPrepare')
   check(#s.takes==1 and s.takes[1].status=='kept','Cancel preparation preserves the recorded take')
   command('prepareTake',{kind='new',session=s.id,take=t.id});command('countin',{value=false});command('recordPrepared');stage=7
  elseif stage==7 and state.elapsed>1.3 then
   snapshot('another-take');command('stop')
   local s,t=M.mix_take(core);check(#s.takes==2 and t.parent==nil and #t.items==1,'Another take records independently')
   command('prepareTake',{kind='part',session=s.id,take=t.id});command('select',{input='2',value=true});command('recordPrepared');stage=8
  elseif stage==8 and state.elapsed>1.3 then
   snapshot('adding-part');command('stop')
   local s,t=M.mix_take(core);check(t.parent==s.takes[2].id and #t.layers==2,'Add part keeps the previous arrangement')
   command('discard',{session=s.id,take=t.id})
   check(core.mode=='review' and core.take==s.takes[2].id and t.status=='discarded' and s.takes[1].id==savedFirst and s.takes[1].status=='kept','Discard latest returns to the parent arrangement and preserves earlier takes')
   for _,take in ipairs(s.takes)do check(#take.items>0,'Audio metadata retained for '..take.id)end
   command('done');snapshot('done');finish(true);return
  end
 end
 reaper.defer(function()local ok,why=xpcall(run,debug.traceback);if not ok then finish(false,why)end end)
end
local ok,why=xpcall(run,debug.traceback);if not ok then finish(false,why)end
''',encoding='utf-8')
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    proc=subprocess.Popen([str(executable),'-newinst','-nosplash','-noactivate','-cfgfile',str(ini),str(script)],
                          startupinfo=startup,creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    print(f'Private Dummy Audio REAPER PID {proc.pid}; artifacts {folder}',flush=True)
    try:
        deadline=time.monotonic()+65
        while time.monotonic()<deadline and proc.poll()is None and not(folder/'result.json').exists():time.sleep(.1)
        result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    finally:
        if proc.poll()is None:proc.kill();proc.wait(timeout=10)
    assert result['ok'],result.get('error')
    recordings=list(folder.glob('library.RPP.recordings/*/*/*.wav'))
    assert len(recordings)>=3,'Native capture files missing'
    for path in recordings:
        with wave.open(str(path),'rb') as audio:assert audio.getnframes()>0
    verify_browser(result,folder)
    print(json.dumps({'ok':True,'device':result['device'],'checks':result['checks'],
                      'recordings':len(recordings),'artifacts':str(folder)},indent=2))


if __name__=='__main__':main()
