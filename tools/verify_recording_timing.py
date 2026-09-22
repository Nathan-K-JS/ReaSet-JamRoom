"""Native output-capture timing proof in a disposable project; no X32 latency claim."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import wave
import numpy as np
ROOT=Path(__file__).resolve().parent.parent

def main():
    folder=Path(tempfile.mkdtemp(prefix='reaset-timing-'))
    axis=np.arange(24000)/48000
    pulse=np.where(axis<.04,np.sin(2*np.pi*1500*axis)*np.exp(-axis*110)*.35,0)
    with wave.open(str(folder/'pulse.wav'),'wb') as f:
        f.setparams((1,2,48000,0,'NONE','not compressed'));f.writeframes((pulse*32767).astype('<i2').tobytes())
    source=r"""
local root,folder=ROOT,FOLDER
local M=dofile(root..'/Requirements/ReaSet_RecordingCore.lua')
local original=reaper.EnumProjects(-1,'');local changes=reaper.GetProjectStateChangeCount(original);local cursor=reaper.GetCursorPosition()
local inputs=reaper.GetNumAudioInputs;local scratch,core,step,started=nil,nil,0,0
local rows={};local count=0
local function finish(ok,why)
 if scratch then
  reaper.SelectProjectInstance(scratch);reaper.Main_OnCommand(1016,0)
  if core then core:restore_options();core:park();core:release_device()end
  reaper.Main_SaveProjectEx(0,folder..'/timing.RPP',8);reaper.Main_OnCommand(40860,0)
 end
 reaper.GetNumAudioInputs=inputs;reaper.SelectProjectInstance(original)
 local same=reaper.GetProjectStateChangeCount(original)==changes and reaper.GetCursorPosition()==cursor
 M.write(folder..'/result.json',M.J.encode({ok=ok and same,error=tostring(why or ''),rows=rows,original_unchanged=same}))
end
local function run()
 if step==0 then
  assert(reaper.GetPlayState()==0,'Stop REAPER first')
  reaper.Main_OnCommand(40859,0);scratch=reaper.EnumProjects(-1,'')
  reaper.Main_SaveProjectEx(0,folder..'/timing.RPP',8)
  reaper.SetProjExtState(0,'ReaSet','projectId',M.guid())
  reaper.AddProjectMarker2(0,true,0,.5,'Timing proof',1,0)
  reaper.InsertTrackAtIndex(0,false);local backing=reaper.GetTrack(0,0)
  reaper.GetSetMediaTrackInfo_String(backing,'P_NAME','[JR:GTR1] Timing pulse',true)
  reaper.SetMediaTrackInfo_Value(backing,'B_MAINSEND',0)
  local it=reaper.AddMediaItemToTrack(backing);local tk=reaper.AddTakeToMediaItem(it)
  reaper.SetMediaItemTake_Source(tk,reaper.PCM_Source_CreateFromFile(folder..'/pulse.wav'))
  reaper.SetMediaItemInfo_Value(it,'D_LENGTH',.5)
  reaper.InsertTrackAtIndex(1,false);local click=reaper.GetTrack(0,1)
  M.ext(click,'ReaSetCountIn','1',true);reaper.SetMediaTrackInfo_Value(click,'B_MAINSEND',0);reaper.CreateTrackSend(click,nil)
  -- Record native summed output containing click + backing pulse. No physical input.
  local create=M.part_track
  M.part_track=function(self,p)
   local existed=M.tracks()[p.id];local tr=create(self,p)
   if not existed then
    reaper.CreateTrackSend(backing,tr);reaper.CreateTrackSend(click,tr)
    reaper.SetTrackSendInfo_Value(tr,1,0,'D_VOL',0)
   end
   return tr
  end
  core=M.new();core:setup();core.db.inputs[1].selected=true
  reaper.GetNumAudioInputs=function()return 16 end
  local arm=core.arm
  core.arm=function(self,t)local n=arm(self,t);for _,tr in pairs(M.tracks())do reaper.SetMediaTrackInfo_Value(tr,'I_RECMODE',1)end;return n end
  step=1
 end
 if step==1 then
  count=count+1
  if count>40 then finish(true);return end
  if count==21 then
   reaper.SetProjectMarker2(0,1,true,4,4.5,'Timing proof')
   reaper.SetMediaItemInfo_Value(reaper.GetTrackMediaItem(reaper.GetTrack(0,0),0),'D_POSITION',4)
  end
  core.mode='idle';core.db.countin=true
  -- Two tempo/rate combinations and a nonzero-region case, twenty starts each.
  local bpm=count<=20 and 240 or 137
  reaper.SetProjExtState(0,'ReaSetTK','bpm:Timing proof',tostring(bpm))
  reaper.CSurf_OnPlayRateChange(count<=20 and 1 or .8)
  core:begin(M.P.songs()[1].key)
  local s,t=M.mix_take(core)
  started=t.origin;step=2
  -- Deliberately stall the UI/controller during the lead-in. Native audio continues.
  local untilTime=reaper.time_precise()+.13
  while reaper.time_precise()<untilTime do end
 elseif step==2 then
  core:tick()
  if core.mode=='review' or reaper.GetPlayPosition()>started+.25 then
   if core.mode~='review' then core:command({project=core.id,op='stop'})end
   local s,t=M.mix_take(core);assert(#t.items>0,'No timing capture')
   local tr=M.tracks()[t.dest['1']];local it=reaper.GetTrackMediaItem(tr,0);local tk=reaper.GetActiveTake(it)
   rows[#rows+1]={file=reaper.GetMediaSourceFileName(reaper.GetMediaItemTake_Source(tk),''),lead=t.leadin/s.rate,beat=(count<=20 and .25 or 60/137)/s.rate}
   step=1
  end
 end
 reaper.defer(function()local ok,err=xpcall(run,debug.traceback);if not ok then finish(false,err)end end)
end
local ok,err=xpcall(run,debug.traceback);if not ok then finish(false,err)end
""".replace('ROOT',json.dumps(ROOT.as_posix())).replace('FOLDER',json.dumps(folder.as_posix()))
    script=folder/'verify.lua';script.write_text(source)
    subprocess.Popen(['C:/Program Files/REAPER (x64)/reaper.exe','-nonewinst',str(script)])
    for _ in range(1500):
        if (folder/'result.json').exists():break
        time.sleep(.2)
    result=json.loads((folder/'result.json').read_text());assert result['ok'],result
    residuals=[]
    for row in result['rows']:
        raw=subprocess.run(['ffmpeg','-v','error','-i',row['file'],'-ac','1','-ar','48000','-f','f32le','-'],capture_output=True,check=True).stdout
        samples=np.abs(np.frombuffer(raw,dtype='<f4'))
        active=np.flatnonzero(samples>.015)
        starts=active[np.r_[True,np.diff(active)>2400]]/48000
        # Last two pulses straddle the lead-in / recorded backing boundary.
        assert len(starts)>=8,(row,starts.tolist())
        residuals.append(float(starts[-1]-starts[-2]-row['beat']))
    assert len(residuals)==40
    spread=max(residuals)-min(residuals)
    assert max(abs(x) for x in residuals)<.001, residuals
    print(json.dumps({'starts':40,'max_boundary_error_ms':max(abs(x) for x in residuals)*1000,'spread_ms':spread*1000,'original_unchanged':True,'artifacts':str(folder)},indent=2))

if __name__=='__main__':main()
