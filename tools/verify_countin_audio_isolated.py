"""Measure native count-in AND following click in private Dummy Audio captures.

Fresh synthetic library, copied code/SWS binary, private configuration, no ports
or hardware routes. Only the newly spawned process is closed; evidence is kept.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import wave

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def main():
    executable = Path('C:/Program Files/REAPER (x64)/reaper.exe')
    sws = Path(os.environ['APPDATA'])/'REAPER/UserPlugins/reaper_sws-x64.dll'
    assert executable.is_file() and sws.is_file()
    folder = Path(tempfile.mkdtemp(prefix='reaset-countin-audio-')).resolve()
    resource = folder/'resource'
    (resource/'UserPlugins').mkdir(parents=True)
    shutil.copy2(sws, resource/'UserPlugins'/sws.name)
    shutil.copytree(ROOT/'Requirements', folder/'code/Requirements')
    ini = resource/'reaper.ini'
    ini.write_text('[REAPER]\nwnd_state=2\nnosplash=1\nloadlastproj=0\n'
                   '[audioconfig]\nmode=4\ndummy_srate=48000\ndummy_blocksize=512\n')
    cases = [
        dict(name='song-103', beat=60/103, phase=.34, rate=1),
        dict(name='song-150', beat=.4, phase=.12, rate=1),
        dict(name='song-slower', beat=.4, phase=.12, rate=.8),
        dict(name='song-faster', beat=.4, phase=.12, rate=1.2),
        dict(name='song-trim-stretch', beat=.5, phase=.2, rate=1, offset=.7, takeRate=1.25),
        dict(name='song-delayed-first-beat', beat=.8, phase=1.3, rate=1),
        dict(name='song-variable-opening', beat=.784, phase=1.3, rate=1,
             sourceBeats=[1.3,2.12,2.9,3.696,4.484,5.26,6.04,6.78,7.584,8.368]),
        dict(name='song-stale-report', beat=.375, phase=.12, rate=1, stale=True),
        dict(name='song-muted-click', beat=.8, phase=1.3, rate=1, muted=True, bpm=150),
        dict(name='song-muted-click-slower', beat=.8, phase=1.3, rate=.8, muted=True, bpm=150),
        dict(name='free-76', beat=60/76, phase=0, rate=1, free=True, beats=4),
        dict(name='free-137-three', beat=60/137, phase=0, rate=.6, free=True, beats=3),
    ]
    for case in cases:
        beats = case.get('sourceBeats') or [case['phase'] + i*case['beat'] for i in range(40)]
        axis = np.arange(1920)/48000
        pulse = np.sin(2*np.pi*1000*axis)*np.exp(-axis*110)*.35
        samples = np.zeros(48000*35)
        for beat in beats:
            start = round(beat*48000)
            samples[start:start+len(pulse)] += pulse
        with wave.open(str(folder/(case['name']+'.wav')), 'wb') as audio:
            audio.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            audio.writeframes((samples*32767).astype('<i2').tobytes())
        report = [.2+i*.75 for i in range(40)] if case.get('stale') else beats
        (folder/(case['name']+'-review.json')).write_text(json.dumps({'beats':report}))
    (folder/'cases.json').write_text(json.dumps(cases))
    script = folder/'worker.lua'
    script.write_text('local folder='+json.dumps(folder.as_posix())+'\n'+r'''
local M,core,click,item,case,songKey,idx,stage,started=nil,nil,nil,nil,nil,nil,0,0,reaper.time_precise()
local result={rows={}}
local J=dofile(folder..'/code/Requirements/ReaSet_JSON.lua')
local function read(path)local f=assert(io.open(path,'rb'));local s=f:read('*a');f:close();return s end
local cases=J.decode(read(folder..'/cases.json'))
local function finish(ok,why)
 if core then pcall(function()if core.db.active then core:command({op='stop',project=core.id})end;core:park();core:release_device()end)end
 result.ok=ok;result.error=not ok and tostring(why)or nil
 local f=assert(io.open(folder..'/result.json','wb'));f:write(J.encode(result));f:close()
end
local function run()
 assert(reaper.time_precise()-started<130,'Private native audio test timed out')
 if stage==0 then
  local resource=reaper.GetResourcePath():gsub('\\','/')
  assert(resource:lower()==(folder..'/resource'):lower(),'Private resource guard failed')
  local ok,device=reaper.GetAudioDeviceInfo('MODE');assert(ok and device=='Dummy Audio','Dummy Audio guard failed')
  local _,path=reaper.EnumProjects(-1,'')
  assert(path=='' and reaper.CountTracks(0)==0 and reaper.GetPlayState()==0 and not reaper.EnumProjects(1,''),'Private empty project required')
  assert(reaper.SNM_GetIntConfigVar,'Private SWS required')
  result.device=device;result.resource=resource;result.version=reaper.GetAppVersion()
  reaper.GetNumAudioInputs=function()return 2 end -- Record internal output, never physical inputs.
  reaper.SetProjExtState(0,'ReaSet','projectId','isolated-countin-audio')
  reaper.AddProjectMarker2(0,true,120,155,'Synthetic song',1,0)
  reaper.AddProjectMarker2(0,true,200,235,'Other cued song',2,0)
  reaper.InsertTrackAtIndex(0,false);click=reaper.GetTrack(0,0)
  reaper.GetSetMediaTrackInfo_String(click,'P_NAME','[JR:CLICK] Synthetic click',true)
  reaper.SetMediaTrackInfo_Value(click,'B_MAINSEND',0)
  item=reaper.AddMediaItemToTrack(click);reaper.AddTakeToMediaItem(item)
  reaper.SetMediaItemInfo_Value(item,'D_POSITION',120);reaper.SetMediaItemInfo_Value(item,'D_LENGTH',35)
  for _,k in ipairs({'D_FADEINLEN','D_FADEOUTLEN','D_FADEINLEN_AUTO','D_FADEOUTLEN_AUTO'})do reaper.SetMediaItemInfo_Value(item,k,0)end
  local other=reaper.AddMediaItemToTrack(click);local otherTake=reaper.AddTakeToMediaItem(other)
  reaper.SetMediaItemTake_Source(otherTake,assert(reaper.PCM_Source_CreateFromFile(folder..'/song-150.wav')))
  reaper.SetMediaItemInfo_Value(other,'D_POSITION',200);reaper.SetMediaItemInfo_Value(other,'D_LENGTH',35)
  reaper.SetProjExtState(0,'ReaSetTK','bpm:Synthetic song','87') -- Deliberately unrelated project/import tempo.
  reaper.SetEditCurPos(120,false,false);reaper.Main_SaveProjectEx(0,folder..'/library.RPP',8)
  M=dofile(folder..'/code/Requirements/ReaSet_RecordingCore.lua');J=M.J;core=M.new();core:setup()
  local arm=core.arm
  core.arm=function(self,t)
   local n=arm(self,t)
   for _,tr in pairs(M.tracks())do reaper.SetMediaTrackInfo_Value(tr,'I_RECMODE',1)end
   return n
  end
  local native=core.start_native
  core.start_native=function(self)
   local s,t=M.mix_take(self);local dest=M.tracks()[t.dest['1']]
   for i=0,reaper.CountTracks(0)-1 do
    local tr=reaper.GetTrack(0,i)
    for n=reaper.GetTrackNumSends(tr,1)-1,0,-1 do reaper.RemoveTrackSend(tr,1,n)end
    reaper.SetMediaTrackInfo_Value(tr,'B_MAINSEND',0)
    if tr==click or M.ext(tr,'ReaSetCountIn',nil,true)=='1' or M.ext(tr,'ReaSetJamClick',nil,true)=='1' then
     for n=reaper.GetTrackNumSends(tr,0)-1,0,-1 do reaper.RemoveTrackSend(tr,0,n)end
     reaper.CreateTrackSend(tr,dest)
    end
   end
   return native(self)
  end
  for _,c in ipairs(core.db.inputs)do c.selected=c.id=='1' end
  core:prepare_device();stage=1
 elseif stage==1 and core.deviceState=='ready' then
  idx=idx+1;case=cases[idx];if not case then finish(true);return end
  local tk=reaper.GetActiveTake(item)
  reaper.SetMediaItemTake_Source(tk,assert(reaper.PCM_Source_CreateFromFile(folder..'/'..case.name..'.wav')))
  reaper.SetMediaItemTakeInfo_Value(tk,'D_PLAYRATE',case.takeRate or 1)
  reaper.SetMediaItemTakeInfo_Value(tk,'D_STARTOFFS',case.offset or 0)
  reaper.SetMediaItemInfo_Value(item,'B_MUTE',case.muted and 1 or 0)
  reaper.SetProjExtState(0,'ReaSetTK','bpm:Synthetic song',tostring(case.bpm or 87))
  reaper.CSurf_OnPlayRateChange(case.rate)
  reaper.SetEditCurPos(200,false,false) -- Confirm the explicitly armed song owns the count-in.
  core.mode='idle';core.db.countin=true
  if case.free then core:jam_settings({bpm=math.floor(60/case.beat+.5),beats=case.beats,click=true})end
  core:begin(case.free and 'freejam' or M.P.songs()[1].key);stage=2
 elseif stage==2 then
  local s,t=M.mix_take(core)
  if reaper.GetPlayPosition()>t.origin+2.5 then
   core:command({op='stop',project=core.id})
   local dest=M.tracks()[t.dest['1']];local recorded=reaper.GetTrackMediaItem(dest,reaper.CountTrackMediaItems(dest)-1)
   assert(recorded,'Missing native output recording')
   local tk=reaper.GetActiveTake(recorded)
   result.rows[#result.rows+1]={case=case,file=reaper.GetMediaSourceFileName(reaper.GetMediaItemTake_Source(tk),''),lead=t.leadin,rate=s.rate,countinBpm=t.countinBpm}
   core:stop_preview();core.mode='idle';stage=1
  end
 end
 if core then core:tick()end
 reaper.defer(function()local ok,why=xpcall(run,debug.traceback);if not ok then finish(false,why)end end)
end
local ok,why=xpcall(run,debug.traceback);if not ok then finish(false,why)end
''', encoding='utf-8')
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    proc = subprocess.Popen([str(executable), '-newinst', '-nosplash', '-noactivate', '-cfgfile', str(ini), str(script)],
                            startupinfo=startup, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    print(f'Private Dummy Audio PID {proc.pid}; evidence {folder}', flush=True)
    try:
        deadline = time.monotonic()+140
        while time.monotonic()<deadline and proc.poll() is None and not (folder/'result.json').exists():
            time.sleep(.1)
        result = json.loads((folder/'result.json').read_text())
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
    assert result['ok'], result.get('error')
    failures = []
    for row in result['rows']:
        raw = subprocess.run(['ffmpeg','-v','error','-i',row['file'],'-ac','1','-ar','48000','-f','f32le','-'],
                             capture_output=True, check=True).stdout
        active = np.flatnonzero(np.abs(np.frombuffer(raw,dtype='<f4'))>.015)
        starts = active[np.r_[True,np.diff(active)>2400]]/48000
        case = row['case']
        beat = (60/case['bpm'] if case.get('muted') else case['beat']/case.get('takeRate',1))/row['rate']
        lead = row['lead']/row['rate']
        count = 2*case.get('beats',4)
        row['onsets'] = starts.tolist()
        row['expected_beat'] = beat
        assert abs(row['countinBpm']-60/beat)<.02, row
        before = starts[starts<lead-.001]
        after = starts[starts>=lead-.001]
        errors = []
        if case.get('muted'):
            assert len(before)==count and len(after)==0, (case,starts)
            errors = (np.diff(before)-beat).tolist()
            assert max(map(abs,errors))<.002, (case,errors)
        elif len(before)!=count or len(after)<2:
            failures.append((case['name'],'pulse count',len(before),len(after)))
        else:
            errors = (np.diff(np.r_[before,after[:2]])-beat).tolist()
            if max(abs(v) for v in errors)>.002:
                failures.append((case['name'],'beat/boundary errors',errors))
        row['errors'] = errors
        # Check the audible song pulses too, against the source timestamps, not
        # a constant-tempo assumption for songs with a changing opening tempo.
        source = case.get('sourceBeats') or [case['phase']+i*case['beat'] for i in range(40)]
        source = [(v-case.get('offset',0))/case.get('takeRate',1)/row['rate'] for v in source]
        source = [lead+v for v in source if v>=-.000001]
        if not case.get('muted'):
            actual_song = starts[starts>=source[0]-.002]
            matched = min(3,len(actual_song))
            assert matched>=2, (case, starts)
            source_errors = np.abs(actual_song[:matched]-source[:matched])
            assert max(source_errors)<.002, (case, source_errors)
            row['source_errors'] = source_errors.tolist()
        print(json.dumps({'case':case['name'],'countin_bpm':60/beat,
                          'pulse_count':len(starts),'max_error_ms':max(map(abs,errors),default=0)*1000}), flush=True)
    (folder/'analysis.json').write_text(json.dumps(result,indent=2))
    assert not failures, failures
    print(f'PASS: {len(result["rows"])} native count-in/transition captures; {folder}')


if __name__ == '__main__':
    main()
