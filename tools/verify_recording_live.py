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
  M.write(folder..'/result.json',M.J.encode({ok=ok and cleaned and unchanged,error=tostring(why or err or ''),original_unchanged=unchanged,original_changes={before=changes,after=reaper.GetProjectStateChangeCount(original)},original_cursor={before=cursor,after=reaper.GetCursorPosition()},checks=checks}))
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
    local incoming=reaper.AddMediaItemToTrack(reaper.GetTrack(0,0));local incoming_take=reaper.AddTakeToMediaItem(incoming)
    reaper.SetMediaItemTake_Source(incoming_take,reaper.PCM_Source_CreateFromFile(folder..'/backing.wav'))
    reaper.SetMediaItemInfo_Value(incoming,'D_POSITION',12);reaper.SetMediaItemInfo_Value(incoming,'D_LENGTH',1)
    reaper.SetMediaItemInfo_Value(incoming,'D_VOL',.5);M.P.reconcile();M.P.reconcile()
    check(math.abs(reaper.GetMediaItemInfo_Value(incoming,'D_VOL')-.4)<.00001,'Newly imported stem receives saved gain once and keeps its relative level')
    reaper.DeleteTrackMediaItem(reaper.GetTrack(0,0),incoming)
    reaper.Main_SaveProject(0,false);reaper.Main_openProject('noprompt:'..folder..'/scratch.RPP')
    check(M.P.songs()[1].key==songs[1].key and math.abs(M.P.gain(M.P.songs()[1])-.8)<.00001,'Song identity and volume survive reopening the RPP')
    core=M.new()
    check(not core:auto_setup() and reaper.CountTracks(0)==2,'Automatic setup leaves non-Jam-Room projects alone')
    reaper.GetSetMediaTrackInfo_String(reaper.GetTrack(0,0),'P_NAME','PB DRUMS',true)
    reaper.GetSetMediaTrackInfo_String(reaper.GetTrack(0,1),'P_NAME','PB CLICK',true)
    local saved_root=core.root;core.root=nil
    check(not core:auto_setup(),'Automatic setup waits for a saved project')
    core.root=saved_root;core.mode='countin'
    check(not core:auto_setup(),'Automatic setup waits until recording work is idle')
    core.mode='idle';reaper.SetProjExtState(0,'ReaSet','recordingProject','1')
    check(not core:auto_setup(),'Automatic setup leaves exported recording projects alone')
    reaper.SetProjExtState(0,'ReaSet','recordingProject','')
    check(core:auto_setup(),'Saved Jam Room project automatically creates its recording template')
    reaper.GetSetMediaTrackInfo_String(reaper.GetTrack(0,0),'P_NAME','[JR:GTR1] Guitar',true)
    reaper.GetSetMediaTrackInfo_String(reaper.GetTrack(0,1),'P_NAME','[JR:CLICK] Click',true)
    check(not core:auto_setup(),'Automatic setup runs only once per project')
    local cfgtrack=M.tracks()['1'];reaper.SetMediaTrackInfo_Value(cfgtrack,'D_VOL',.42)
    core:auto_setup()
    check(math.abs(reaper.GetMediaTrackInfo_Value(cfgtrack,'D_VOL')-.42)<.00001,'Later startup checks preserve customized recording levels')
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
    reaper.CSurf_OnPlayRateChange(.8)
    core:begin(songs[1].key)
    check(core.mode=='countin' and reaper.GetPlayState()==0,'Audible count-in leaves the setlist transport stopped')
    core:command({project=core.id,op='stop'})
    check(core.mode=='idle' and core:state().pending==0 and not core:state().notice,'Cancelled count-in returns to setup without an export reminder')
    check(#M.J.decode(M.read(core.root..'/index.json')).sessions==0,'Empty count-in cleanup is durable')
    core:begin(songs[1].key)
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
    M.owned_items(function(it)
      check(math.abs(reaper.GetMediaItemTakeInfo_Value(reaper.GetActiveTake(it),'D_PLAYRATE')*.8-1)<.00001,'Recorded item compensates for changed song speed')
    end)
    core.db.countin=false
    core:command({project=core.id,revision=core.revision,op='keep',session=s.id,take=t.id})
    stage=4;started=reaper.time_precise()
  elseif stage==4 and reaper.time_precise()-started>1 then
    reaper.Main_OnCommand(1016,0);core:finish()
    local s=core.db.sessions[1]
    check(#s.takes==2 and #s.takes[2].items>=2,'Keep records an independent second multitrack pass')
    core:command({project=core.id,revision=core.revision,op='retry',session=s.id,take=s.takes[2].id})
    stage=5;started=reaper.time_precise()
  elseif stage==5 and reaper.time_precise()-started>1 then
    reaper.Main_OnCommand(1016,0);core:finish()
    local s=core.db.sessions[1];local t=s.takes[1]
    check(#s.takes==3 and s.takes[2].status=='discarded' and #s.takes[3].items>=2,'Discard and retry preserves older takes and creates a third pass')
    local last=s.takes[3];local duration=last.duration
    M.owned_items(function(it,tr,tag)if tag==s.id..'/'..last.id then reaper.DeleteTrackMediaItem(tr,it)end end)
    last.items=M.J.array();last.status='recording';core.db.active={session=s.id,take=last.id};core:save(false)
    core=M.new();s=core.db.sessions[1];last=s.takes[3]
    check(#last.items>=2 and not last.unresolved and last.status=='recovered','Interrupted pass recovers native media missing from its journal')
    check(math.abs(last.duration-duration)<.1,'Interrupted media recovery retains non-unit playrate alignment')
    check(core:state().pending==1,'Restart discovers unexported session')
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
    local expected=0;for _,tk in ipairs(s.takes)do expected=expected+#tk.items end
    check(restored==expected,'Deleted session restores from its saved item chunks')
    M.owned_items(function(it,tr)reaper.DeleteTrackMediaItem(tr,it)end)
    reaper.Main_SaveProject(0,false)
    core=M.new();s=core.db.sessions[1]
    local recovered=0;M.owned_items(function()recovered=recovered+1 end)
    check(recovered==expected,'Session journal recovers takes missing from an older RPP')
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
    core.db.inputs[1].name=string.rep(utf8.char(0xe9,0x1f3b5),220);core:save(false)
    -- Run the actual wire bridge in this scratch tab with a controlled defer
    -- scheduler, so it cannot move on to the user's project after this test.
    local native_defer,native_exit,native_time=reaper.defer,reaper.atexit,reaper.time_precise
    local next_bridge,exit_bridge,offset=nil,nil,0
    reaper.defer=function(fn)next_bridge=fn end
    reaper.atexit=function(fn)exit_bridge=fn end
    reaper.time_precise=function()return native_time()+offset end
    local function wire_state()
      local gen,count,slot=reaper.GetExtState('ReaSetRec','meta'):match('^(%d+):(%d+):(%d+)$')
      local raw=''
      for i=0,tonumber(count)-1 do local value=reaper.GetExtState('ReaSetRec','d'..slot..'_'..i);assert(value:match('^(%d+):')==gen);assert(utf8.len(value),'Wire chunk splits a Unicode character');raw=raw..value:match('^%d+:(.*)$')end
      return M.J.decode(raw)
    end
    local worked,why=pcall(function()
      dofile(root..'/Requirements/ReaSet_Recording.lua')
      local state=wire_state()
      check(state.inputs[1].name==core.db.inputs[1].name,'Unicode names survive individually valid wire chunks')
      local c={project=state.project,revision=state.revision,nonce='gain-once',op='gain',song=state.songs[1].key,value=.7}
      reaper.SetExtState('ReaSetRec','want',M.J.encode(c),false);offset=offset+.2;next_bridge()
      state=wire_state();check(state.ack==c.nonce and math.abs(state.songs[1].gain-.7)<.00001,'Wire bridge acknowledges confirmed song volume')
      c.value=.2;reaper.SetExtState('ReaSetRec','want',M.J.encode(c),false);offset=offset+.2;next_bridge()
      check(math.abs(wire_state().songs[1].gain-.7)<.00001,'Duplicate tablet command cannot run twice')
      c.nonce='stale-tablet';reaper.SetExtState('ReaSetRec','want',M.J.encode(c),false);offset=offset+.2;next_bridge()
      check(wire_state().error~=nil and math.abs(wire_state().songs[1].gain-.7)<.00001,'Stale tablet revision is rejected without changing gain')
      c.nonce='wrong-project';c.project='different';c.revision=wire_state().revision
      reaper.SetExtState('ReaSetRec','want',M.J.encode(c),false);offset=offset+.2;next_bridge()
      check(wire_state().error~=nil and math.abs(wire_state().songs[1].gain-.7)<.00001,'Commands cannot operate on a different project')
    end)
    if exit_bridge then exit_bridge()end
    reaper.defer,reaper.atexit,reaper.time_precise=native_defer,native_exit,native_time
    assert(worked,why)

    -- Free-jam coverage uses native output capture to exercise four independent
    -- channels even on a development audio device without the physical X32.
    core=M.new();reaper.GetNumAudioInputs=function()return 32 end
    local arm=core.arm
    core.arm=function(self)local n=arm(self);for _,tr in pairs(M.tracks())do reaper.SetMediaTrackInfo_Value(tr,'I_RECMODE',1)end;return n end
    for i,c in ipairs(core.db.inputs)do c.selected=i<=4 end
    core.db.countin=true;core.db.recordMode='freejam'
    core:jam_settings({bpm=137,beats=3,click=true})
    reaper.CSurf_OnPlayRateChange(.8)
    core:command({project=core.id,revision=core.revision,op='record'})
    local s=core:session(core.selected)
    check(s.song.free and s.rate==1 and s.semis==0 and #s.takes[1].inputs==4,'Free jam records four selected mics at normal speed')
    check(core.mode=='countin' and reaper.GetPlayState()==0,'Free jam supports independent two-bar count-in')
    check(core.jamClick and reaper.GetMediaItemInfo_Value(core.jamClick,'B_LOOPSRC')==1,'Free jam creates a transport-synchronised looping click')
    check(reaper.GetMediaItemInfo_Value(reaper.GetTrackMediaItem(reaper.GetTrack(0,0),0),'B_MUTE')==1,'Free jam silences library media')
    stage=20;started=reaper.time_precise()
  elseif stage==20 then
    core:tick()
    if core.mode=='recording' then stage=21;started=reaper.time_precise()end
  elseif stage==21 and reaper.time_precise()-started>.5 then
    core:tick();check(core.mode=='recording','Free jam has no song-end stop')
    core:command({project=core.id,revision=core.revision,op='pause'})
    check((reaper.GetPlayState()&2)==2,'Free jam and its click pause with native transport')
    stage=22;started=reaper.time_precise()
  elseif stage==22 and reaper.time_precise()-started>.2 then
    core:command({project=core.id,revision=core.revision,op='pause'})
    stage=23;started=reaper.time_precise()
  elseif stage==23 and reaper.time_precise()-started>.5 then
    core:command({project=core.id,op='stop'})
    local s=core:session(core.selected);local t=s.takes[1]
    check(#t.items==4 and t.duration>0 and s.song.finish>s.song.start,'Only four selected mic tracks are captured; jam duration is saved')
    check(not core.jamClick and math.abs(reaper.Master_GetPlayRate(0)-.8)<.0001,'Stop removes temporary click and restores playback speed')
    check(reaper.GetMediaItemInfo_Value(reaper.GetTrackMediaItem(reaper.GetTrack(0,0),0),'B_MUTE')==0,'Stop restores library mute state')
    core.db.countin=false
    core:command({project=core.id,revision=core.revision,op='keep',session=s.id,take=t.id})
    check(core.mode=='recording' and core.jamClick~=nil,'Keep another take retains click with count-in off')
    stage=24;started=reaper.time_precise()
  elseif stage==24 and reaper.time_precise()-started>1 then
    -- Simulate restart after native Stop but before controller acknowledgement.
    reaper.Main_OnCommand(1016,0);core=M.new()
    local s=core:session(core.selected)
    check(s.takes[2].status=='recovered' and #s.takes[2].items==4,'Free jam recovers an interrupted take on restart')
    check(not core.jamClick and core.db.jam.bpm==137,'Restart removes temporary click and remembers jam settings')
    core:review(s.id,s.takes[1].id)
    check(reaper.GetMediaItemInfo_Value(reaper.GetTrackMediaItem(reaper.GetTrack(0,0),0),'B_MUTE')==1,'Free-jam review excludes backing songs')
    core:park();M.export(core,s)
    check(s.exported~=nil,'Free jam uses verified export and cleanup')
    reaper.Main_OnCommand(40859,0);local exported=reaper.EnumProjects(-1,'')
    reaper.Main_openProject('noprompt:'..s.exported)
    local num,den,bpm=reaper.TimeMap_GetTimeSigAtTime(0,0)
    check(num==3 and den==4 and math.abs(bpm-137)<.001,'Free-jam export preserves chosen tempo and meter')
    check(reaper.CountMediaItems(0)==8,'Free-jam export contains both four-mic takes without backing or click')
    reaper.Main_OnCommand(40860,0);reaper.SelectProjectInstance(scratch)
    -- A band can choose different inputs and no click, with count-in alone.
    core.mode='idle';core.db.countin=true;core:jam_settings({bpm=240,beats=2,click=false})
    for i,c in ipairs(core.db.inputs)do c.selected=i==5 or i==6 or i==9 or i==10 end
    local arm=core.arm
    core.arm=function(self)local n=arm(self);for _,tr in pairs(M.tracks())do reaper.SetMediaTrackInfo_Value(tr,'I_RECMODE',1)end;return n end
    core:begin('freejam')
    check(core.mode=='countin' and not core.jamClick,'Band jam can use count-in without continuous click')
    stage=25;started=reaper.time_precise()
  elseif stage==25 then
    core:tick()
    if core.mode=='recording' then stage=26;started=reaper.time_precise()end
  elseif stage==26 and reaper.time_precise()-started>1 then
    core:command({project=core.id,op='stop'})
    local s=core:session(core.selected);local t=s.takes[1]
    check(#t.items==4 and t.inputs[1]=='5' and t.inputs[4]=='10','Band jam captures only selected instruments including stereo pairs')
    core.db.countin=false
    core:command({project=core.id,revision=core.revision,op='retry',session=s.id,take=t.id})
    check(core.mode=='recording' and not core.jamClick and t.status=='discarded','Discard and retry supports no click and no count-in')
    stage=27;started=reaper.time_precise()
  elseif stage==27 and reaper.time_precise()-started>1 then
    core:command({project=core.id,op='stop'})
    local s=core:session(core.selected);local t=s.takes[#s.takes];local count=#t.items
    core:command({project=core.id,revision=core.revision,op='discard',session=s.id,take=t.id})
    check(core.mode=='idle' and reaper.GetPlayState()==0 and t.status=='discarded','Discard returns to setup without recording')
    check(#t.items==count and count>0,'Discard retains recorded audio for recovery')
    core:command({project=core.id,revision=core.revision,op='restoreTake',session=s.id,take=t.id})
    check(t.status=='kept','Discarded take can be restored')
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
    for _ in range(450):
        if result.exists(): break
        time.sleep(.2)
    if not result.exists(): raise RuntimeError('No REAPER result; inspect ' + str(folder))
    data = json.loads(result.read_text()); print(json.dumps(data, indent=2)); print('Artifacts:', folder)
    if not data['ok']: raise SystemExit(1)


if __name__ == '__main__': main()
