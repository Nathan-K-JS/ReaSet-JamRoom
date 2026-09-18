"""Opt-in recording/export integration in a disposable REAPER project tab.

Uses the current audio device's first input, or native track-output capture when
this workstation has no inputs. Leaves the loaded library unchanged.
Run while REAPER is stopped: python tools/verify_recording_live.py
"""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import wave

ROOT = Path(__file__).resolve().parent.parent


def main():
    folder = Path(tempfile.mkdtemp(prefix='reaset-recording-'))
    with wave.open(str(folder / 'backing.wav'), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(b'\0\0' * 24000 * 4)
    source = r'''
local root,folder=ROOT,FOLDER
local M=dofile(root..'/Requirements/ReaSet_RecordingCore.lua')
dofile(root..'/Requirements/ReaSet_RecordingExport.lua')(M)
local original=reaper.EnumProjects(-1,'')
local changes=reaper.GetProjectStateChangeCount(original)
local cursor=reaper.GetCursorPosition()
local lock=reaper.GetExtState('ReaSetRec','lock')
local scratch,core,stage,started,checks=nil,nil,0,0,{}
local real_inputs=reaper.GetNumAudioInputs
local function check(ok,text)assert(ok,text);checks[#checks+1]=text end
local function cleanup(ok,why)
  local cleaned,err=pcall(function()
    if scratch and reaper.ValidatePtr(scratch,'ReaProject*')then
      reaper.SelectProjectInstance(scratch)
      reaper.Main_OnCommand(1016,0)
      if core then core:stop_preview();core:restore_options();core:park()end
      reaper.Main_SaveProjectEx(scratch,folder..'/scratch.RPP',8)
      reaper.Main_OnCommand(40860,0)
    end
  end)
  reaper.SelectProjectInstance(original)
  reaper.SetExtState('ReaSetRec','lock',lock,false)
  reaper.GetNumAudioInputs=real_inputs
  local unchanged=reaper.GetProjectStateChangeCount(original)==changes and reaper.GetCursorPosition()==cursor
  M.write(folder..'/result.json',M.J.encode({ok=ok and cleaned and unchanged,error=tostring(why or err or ''),original_unchanged=unchanged,checks=checks}))
end
local function run()
  if stage==0 then
    assert(reaper.GetPlayState()==0,'Stop REAPER first')
    reaper.Main_OnCommand(40859,0);scratch=reaper.EnumProjects(-1,'')
    reaper.Main_SaveProjectEx(0,folder..'/scratch.RPP',8)
    reaper.SetProjExtState(0,'ReaSet','projectId','recording-smoke-'..M.guid())
    reaper.AddProjectMarker2(0,true,10,14,'Recording smoke',1,0)
    for i,name in ipairs({'[JR:GTR1] Guitar','[JR:CLICK] Click'})do
      reaper.InsertTrackAtIndex(reaper.CountTracks(0),false)
      local tr=reaper.GetTrack(0,reaper.CountTracks(0)-1)
      reaper.GetSetMediaTrackInfo_String(tr,'P_NAME',name,true)
      local it=reaper.AddMediaItemToTrack(tr);reaper.SetMediaItemInfo_Value(it,'D_POSITION',10)
      reaper.SetMediaItemInfo_Value(it,'D_LENGTH',4)
      local tk=reaper.AddTakeToMediaItem(it);reaper.SetMediaItemTake_Source(tk,reaper.PCM_Source_CreateFromFile(folder..'/backing.wav'))
    end
    local songs=M.P.songs();check(#songs==1,'Stable song discovery')
    M.P.reconcile()
    local stem=reaper.GetTrackMediaItem(reaper.GetTrack(0,0),0)
    local click=reaper.GetTrackMediaItem(reaper.GetTrack(0,1),0)
    check(math.abs(reaper.GetMediaItemInfo_Value(stem,'D_VOL')-.65)<.00001,'Default stem gain is 65 percent')
    check(reaper.GetMediaItemInfo_Value(click,'D_VOL')==1,'Click gain unchanged')
    M.P.set(songs[1],0);M.P.set(songs[1],.8);M.P.reconcile()
    check(math.abs(reaper.GetMediaItemInfo_Value(stem,'D_VOL')-.8)<.00001,'Gain survives zero and repeated reconciliation')
    core=M.new();core:setup()
    check(reaper.CountTracks(0)==17,'Creates fourteen default recording tracks in a folder')
    core:setup();check(reaper.CountTracks(0)==17,'Setup does not duplicate recording tracks')
    check(reaper.GetMediaTrackInfo_Value(M.tracks()['9'],'I_RECINPUT')==1032,'EAD10 stereo input 9/10')
    check(reaper.GetMediaTrackInfo_Value(M.tracks()['10'],'I_RECINPUT')==1034,'Keys stereo input 11/12')
    core.db.inputs[1].selected=true;core.db.inputs[2].selected=true;core.db.countin=true
    reaper.SetProjExtState(0,'ReaSetTK','bpm:Recording smoke','300')
    if real_inputs()<2 then
      -- Test-only substitute: REAPER still writes real audio files, but captures
      -- its track output. This does not claim to verify physical X32 inputs.
      reaper.GetNumAudioInputs=function()return 16 end
      local arm=core.arm
      core.arm=function(self)local n=arm(self);for _,id in ipairs({'1','2'})do reaper.SetMediaTrackInfo_Value(M.tracks()[id],'I_RECMODE',1)end;return n end
      checks[#checks+1]='No hardware inputs: using native track-output capture'
    end
    reaper.SetEditCurPos(10,false,false)
    reaper.SetExtState('ReaSetRec','lock',core.id,false)
    core:begin(songs[1].key)
    check(core.mode=='countin' and reaper.GetPlayState()==0,'Audible count-in leaves the setlist transport stopped')
    stage=10;started=reaper.time_precise()
  elseif stage==10 then
    core:tick()
    if core.mode=='recording' then
      check((reaper.GetPlayState()&4)==4,'Native REAPER recording starts after count-in')
      stage=1;started=reaper.time_precise()
    end
  elseif stage==1 and reaper.time_precise()-started>.5 then
    reaper.Main_OnCommand(1008,0)
    check((reaper.GetPlayState()&2)==2,'Native recording pauses')
    stage=2;started=reaper.time_precise()
  elseif stage==2 and reaper.time_precise()-started>.2 then
    reaper.Main_OnCommand(1008,0)
    check((reaper.GetPlayState()&4)==4,'Native recording resumes')
    stage=3;started=reaper.time_precise()
  elseif stage==3 and reaper.time_precise()-started>.5 then
    reaper.Main_OnCommand(1016,0);core:finish()
    local s=core.db.sessions[1];local t=s.takes[1]
    check(#t.items>=2 and t.duration>0,'Native multitrack recording captured and indexed')
    check(M.read(core.root..'/index.json')~=nil,'Session index saved outside RPP')
    core=M.new();check(core:state().pending==1,'Restart discovers unexported session')
    M.owned_items(function(it)check(reaper.GetMediaItemInfo_Value(it,'B_MUTE')==1,'Restart parks recorded media silent')end)
    core:review(s.id,t.id)
    core.backingOn=false;core:audition_mix()
    check(reaper.GetMediaItemInfo_Value(reaper.GetTrackMediaItem(reaper.GetTrack(0,0),0),'B_MUTE')==1,'Review can mute backing independently')
    core:park()
    check(reaper.GetMediaItemInfo_Value(reaper.GetTrackMediaItem(reaper.GetTrack(0,0),0),'B_MUTE')==0,'Review restores rehearsal backing mute')
    s=core.db.sessions[1]
    s.deleted=true;core:save(false);core:remove_session(s)
    local removed=0;M.owned_items(function()removed=removed+1 end)
    check(removed==0,'Delete removes only owned recording items')
    core:restore_session(s)
    local restored=0;M.owned_items(function()restored=restored+1 end)
    check(restored==#s.takes[1].items,'Deleted session restores from its saved item chunks')
    local read=M.read
    M.read=function(path)if path:match('Recording%.RPP$')then return nil end return read(path)end
    local exported=pcall(function()M.export(core,s)end)
    M.read=read
    local retained=0;M.owned_items(function()retained=retained+1 end)
    check(not exported and retained==restored and not s.exported,'Failed export verification retains original recordings')
    M.export(core,s)
    check(s.exported and M.read(s.exported)~=nil,'Self-contained recording project saved and reopened')
    local count=0;M.owned_items(function()count=count+1 end)
    check(count==0,'Verified export clears recording items from setlist')
    check(reaper.CountTrackMediaItems(reaper.GetTrack(0,0))==1,'Original stem remains in setlist')
    check(core:state().pending==0,'Exported session no longer prompts housekeeping')
    cleanup(true);return
  end
  reaper.defer(function()local ok,err=xpcall(run,debug.traceback);if not ok then cleanup(false,err)end end)
end
local ok,err=xpcall(run,debug.traceback);if not ok then cleanup(false,err)end
'''
    source = source.replace('ROOT', json.dumps(ROOT.as_posix())).replace('FOLDER', json.dumps(folder.as_posix()))
    script = folder / 'verify.lua'; script.write_text(source, encoding='utf-8')
    subprocess.Popen(['C:/Program Files/REAPER (x64)/reaper.exe', '-nonewinst', str(script)])
    result = folder / 'result.json'
    for _ in range(250):
        if result.exists(): break
        time.sleep(.2)
    if not result.exists(): raise RuntimeError('No REAPER result; inspect ' + str(folder))
    data = json.loads(result.read_text()); print(json.dumps(data, indent=2)); print('Artifacts:', folder)
    if not data['ok']: raise SystemExit(1)


if __name__ == '__main__': main()
