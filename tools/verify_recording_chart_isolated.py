"""Native count-in preparation in a private Dummy Audio REAPER process.

Creates synthetic media and copies Lua code only. Never starts transport, opens
an existing project, uses web ports, or touches the installed REAPER profile.
Retains its new temporary directory and terminates only the process it creates.
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


def main():
    executable=Path('C:/Program Files/REAPER (x64)/reaper.exe')
    if os.name!='nt' or not executable.is_file():
        raise SystemExit('Requires Windows and the installed REAPER executable')
    folder=Path(tempfile.mkdtemp(prefix='reaset-recording-chart-')).resolve()
    resource=folder/'resource';resource.mkdir()
    ini=resource/'reaper.ini'
    ini.write_text('[REAPER]\nwnd_state=2\nnosplash=1\nloadlastproj=0\n'
                   '[audioconfig]\nmode=4\ndummy_srate=48000\ndummy_blocksize=1024\n',encoding='utf-8')
    shutil.copytree(ROOT/'Requirements',folder/'code'/'Requirements')
    beats=[.12+i*.375 for i in range(24)]
    pcm=[0]*(22050*10)
    for beat in beats:pcm[round(beat*22050)]=16000
    with wave.open(str(folder/'click.wav'),'wb') as out:
        out.setparams((1,2,22050,0,'NONE','not compressed'))
        out.writeframes(struct.pack('<'+'h'*len(pcm),*pcm))
    (folder/'click-review.json').write_text(json.dumps({'beats':beats}),encoding='utf-8')
    script=folder/'worker.lua'
    script.write_text('local folder='+json.dumps(folder.as_posix())+'\n'+r'''
local J=dofile(folder..'/code/Requirements/ReaSet_JSON.lua')
local result={cases={}}
local ok,why=xpcall(function()
 local resource=reaper.GetResourcePath():gsub('\\','/')
 assert(resource:lower()==(folder..'/resource'):lower(),'Private resource guard failed')
 local yes,device=reaper.GetAudioDeviceInfo('MODE')
 assert(yes and device=='Dummy Audio','Dummy Audio guard failed')
 local _,path=reaper.EnumProjects(-1,'')
 assert(path=='' and reaper.CountTracks(0)==0 and reaper.GetPlayState()==0,'Expected private empty project')
 assert(not reaper.EnumProjects(1,''),'Unexpected second project')
 result.device=device;result.resource=resource;result.version=reaper.GetAppVersion()
 local M=dofile(folder..'/code/Requirements/ReaSet_RecordingCore.lua')
 reaper.InsertTrackAtIndex(0,false);local tr=reaper.GetTrack(0,0)
 reaper.GetSetMediaTrackInfo_String(tr,'P_NAME','[JR:CLICK] Synthetic click',true)
 reaper.SetMediaTrackInfo_Value(tr,'B_MAINSEND',0)
 local it=reaper.AddMediaItemToTrack(tr);local tk=reaper.AddTakeToMediaItem(it)
 reaper.SetMediaItemTake_Source(tk,assert(reaper.PCM_Source_CreateFromFile(folder..'/click.wav')))
 reaper.SetMediaItemInfo_Value(it,'D_POSITION',120);reaper.SetMediaItemInfo_Value(it,'D_LENGTH',10)
 reaper.SetProjExtState(0,'ReaSetTK','bpm:Synthetic song','80')
 local self={db={countin=true,active={}},audition={},save=function()end,
   click_output=function()return 0,1 end,jam_click=function()end,
   start_native=function(s)assert(reaper.GetPlayState()==0);s.mode='recording'end}
 dofile(folder..'/code/Requirements/ReaSet_RecordingTimeline.lua')(self,M)
 for i,rate in ipairs({1,.8})do
  reaper.CSurf_OnPlayRateChange(rate)
  local s={song={start=120,finish=130,name='Synthetic song'},folder=folder..'/song-'..i,parts={},takes={}}
  reaper.RecursiveCreateDirectory(s.folder,0)
  local t={id='take-'..i,mix={}}
  self:prepare_timeline(s,t)
  assert(math.abs(t.leadin-3)<.000001,'Song count-in used the unrelated 80 BPM label')
  assert(self.mode=='countin' and reaper.GetPlayState()==0)
  result.cases[#result.cases+1]={file=s.folder..'/count-in.wav',lead=t.leadin,rate=rate,phase=.12,beat=.375}
 end
 local s={song={start=0,finish=10,name='Free jam',free=true,bpm=100,beats=3},folder=folder..'/free',parts={},takes={}}
 reaper.RecursiveCreateDirectory(s.folder,0);local t={id='free',mix={}}
 self:prepare_timeline(s,t);assert(math.abs(t.leadin-3.6)<.000001)
 result.cases[#result.cases+1]={file=s.folder..'/count-in.wav',lead=t.leadin,rate=.8,phase=0,beat=.6}
 result.transport=reaper.GetPlayState()
end,debug.traceback)
result.ok=ok;result.error=not ok and tostring(why)or nil
local f=assert(io.open(folder..'/result.json','wb'));f:write(J.encode(result));f:close()
''',encoding='utf-8')
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    proc=subprocess.Popen([str(executable),'-newinst','-nosplash','-noactivate','-cfgfile',str(ini),str(script)],
                          startupinfo=startup,creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    print(f'Private REAPER PID: {proc.pid}; artifacts: {folder}',flush=True)
    try:
        deadline=time.monotonic()+45
        while time.monotonic()<deadline and proc.poll()is None and not(folder/'result.json').exists():time.sleep(.1)
        result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    finally:
        if proc.poll()is None:proc.kill();proc.wait(timeout=10)
    assert result['ok'],result
    for row in result['cases']:
        with wave.open(row['file'],'rb') as audio:
            sr=audio.getframerate();samples=audio.getnframes()
            pcm=struct.unpack('<'+'h'*samples,audio.readframes(samples))
        active=[i for i,v in enumerate(pcm)if abs(v)>500]
        starts=[active[0]/sr]+[b/sr for a,b in zip(active,active[1:])if b-a>sr*.1]
        assert len(starts)==round(row['lead']/row['beat']),(row,starts)
        errors=[abs(t-row['phase']-i*row['beat']) for i,t in enumerate(starts)]
        assert max(errors)<.001,(row,errors)
        row['max_onset_error_ms']=max(errors)*1000
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
