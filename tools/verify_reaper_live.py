"""Opt-in integration check in a temporary REAPER project tab.

Run while REAPER is stopped: python tools/verify_reaper_live.py
Creates/saves/closes only its scratch project; never updates the loaded library.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import jamroom_chart as chart

ROOT=Path(__file__).resolve().parent.parent


def main():
    folder=Path(tempfile.mkdtemp(prefix='reaset-live-'))
    doc,_=chart.build_document({'duration':60,'lyrics':{'synced':True,'lines':[
        {'time':10,'text':'Here we sing'},{'time':20,'text':''},
        {'time':40,'text':'Here we sing'},{'time':50,'text':''}]}},
        chart.parse_chart('[Intro]\n[ch]C[/ch]\n[Verse]\n[ch]G[/ch]\nHere we sing\n[Solo]\n[ch]Am[/ch] [ch]F[/ch]'),[])
    (folder/'document.json').write_text(json.dumps(doc),encoding='utf-8')
    source=r'''
local root, folder = ROOT, FOLDER
local J=dofile(root..'/Requirements/ReaSet_JSON.lua')
local original=reaper.EnumProjects(-1,'')
local original_changes=reaper.GetProjectStateChangeCount(original)
local original_cursor=reaper.GetCursorPosition()
local scratch,checks=nil,{}
local function check(ok,name)assert(ok,name);checks[#checks+1]=name end
local function read(path)local f=assert(io.open(path,'rb'));local s=f:read('*a');f:close();return s end
local function write(path,text)local f=assert(io.open(path,'wb'));f:write(text);f:close()end
local real_dofile=dofile
local current_job
dofile=function(path)if path:match('jamroom_pending_rechord.lua$')then return current_job end;return real_dofile(path)end
local ok,why=pcall(function()
  assert(reaper.GetPlayState()==0,'Stop REAPER playback first')
  assert(reaper.kbd_getTextFromCmd(40859,0)=='New project tab','Unexpected new-tab action')
  assert(reaper.kbd_getTextFromCmd(40860,0)=='Close current project tab','Unexpected close-tab action')
  reaper.Main_OnCommand(40859,0);scratch=reaper.EnumProjects(-1,'')
  assert(scratch~=original,'Scratch project was not opened')
  assert(reaper.CountTracks(0)==0,'Scratch tab must be empty')
  reaper.SetProjExtState(0,'ReaSet','projectId','reaset-smoke')
  for _,name in ipairs({'lyrics','chords','User recording'})do
    reaper.InsertTrackAtIndex(reaper.CountTracks(0),false)
    local tr=reaper.GetTrack(0,reaper.CountTracks(0)-1)
    reaper.GetSetMediaTrackInfo_String(tr,'P_NAME',name,true)
    local it=reaper.AddMediaItemToTrack(tr)
    reaper.SetMediaItemInfo_Value(it,'D_POSITION',10)
    reaper.SetMediaItemInfo_Value(it,'D_LENGTH',2)
    reaper.ULT_SetMediaItemNote(it,name=='lyrics' and 'old lyric' or name=='chords' and 'C' or 'Keep this recording')
  end
  local user_item=reaper.GetTrackMediaItem(reaper.GetTrack(0,2),0)
  local _,user_before=reaper.GetItemStateChunk(user_item,'',false)
  local id=reaper.AddProjectMarker2(0,true,0,60,'Smoke song',1,0)
  local document=read(folder..'/document.json')
  local function apply(op,extra)
    reaper.RecursiveCreateDirectory(folder..'/'..op,0)
    current_job={project='reaset-smoke',id=id,region='Smoke song',start=0,['end']=60,
      operation=op,before=folder..'/'..op..'/before.json',after=folder..'/'..op..'/after.json',
      receipt=folder..'/'..op..'/receipt.json',document=document,revision=J.decode(document).revision,
      lyrics={{s=10,e=20,text='Here we sing'}},chords={{s=10,e=12,name='G'}}}
    for k,v in pairs(extra or {})do current_job[k]=v end
    real_dofile(root..'/tools/jamroom_song_transaction.lua')
    return J.decode(read(current_job.receipt))
  end
  check(apply('one').status=='ok','Production transaction applies')
  local before=read(folder..'/one/before.json')
  check(apply('one').status=='ok' and before==read(folder..'/one/before.json'),'Retry preserves original backup')
  check(apply('moved',{['end']=61}).status=='error','Changed boundaries rejected')
  local _,user_after=reaper.GetItemStateChunk(user_item,'',false)
  check(user_before==user_after,'Other tracks unchanged')
  check(apply('restore',{restore=folder..'/one/before.json',expected=folder..'/one/after.json'}).status=='ok','Restore actual REAPER item chunks')
  check(reaper.ULT_GetMediaItemNote(reaper.GetTrackMediaItem(reaper.GetTrack(0,0),0))=='old lyric','Original lyric restored')
  check(apply('two').status=='ok','Reapply after restore')
  -- Exercise the persistent chart bridge synchronously, with a private wire
  -- namespace so the running browser bridge is not disturbed.
  local real_set,real_get,real_delete=reaper.SetExtState,reaper.GetExtState,reaper.DeleteExtState
  reaper.SetExtState=function(sec,key,value,persist)real_set(sec=='ReaSetCL' and 'ReaSetSmokeCL' or sec,key,value,persist)end
  reaper.GetExtState=function(sec,key)return real_get(sec=='ReaSetCL' and 'ReaSetSmokeCL' or sec,key)end
  reaper.DeleteExtState=function(sec,key,persist)return real_delete(sec=='ReaSetCL' and 'ReaSetSmokeCL' or sec,key,persist)end
  local tick
  reaper.defer=function(fn)tick=fn end
  local bridge_exit
  reaper.atexit=function(fn)bridge_exit=fn end
  reaper.SetToggleCommandState=function()end
  reaper.SetEditCurPos(10,false,false)
  real_dofile(root..'/Requirements/ReaSet_ChordsLyrics.lua')
  local meta=real_get('ReaSetSmokeCL','meta');local chunks=tonumber(meta:match(':(%d+)$'))
  local parts={};for i=0,chunks-1 do parts[#parts+1]=real_get('ReaSetSmokeCL','d'..i):match('^[^:]+:(.*)$')end
  check(J.decode(table.concat(parts)).document.sections[1].label=='Intro','Bridge publishes structured document')
  local fields={'edit','section',id,2,11,20,'Verse corrected',0,1,J.decode(document).revision,'reaset-smoke','G D'}
  real_set('ReaSetSmokeCL','want',table.concat(fields,'|'),false);tick()
  check(real_get('ReaSetSmokeCL','repair'):match('^edit|ok|')~=nil,'Section edit confirmed')
  local _,edited=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
  check(J.decode(edited).sections[2].start==11 and J.decode(edited).sections[1]['end']==11,'Shared section boundary adjusted')
  fields[1]='stale';real_set('ReaSetSmokeCL','want',table.concat(fields,'|'),false);tick()
  check(real_get('ReaSetSmokeCL','repair'):match('^stale|error|')~=nil,'Stale editor revision rejected')
  local function chart_edit(nonce,action,data,revision)
    local _,blob=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
    local current=J.decode(blob)
    local hex=J.encode(data):gsub('.',function(c)return string.format('%02x',c:byte())end)
    local chunks=0
    for at=1,#hex,384 do
      real_set('ReaSetSmokeCL','edit:'..nonce..':'..chunks,hex:sub(at,at+383),false);chunks=chunks+1
    end
    real_set('ReaSetSmokeCL','want',table.concat({nonce,action,id,revision or current.revision,'reaset-smoke','chunks:'..chunks},'|'),false)
    tick()
    local _,after=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
    return J.decode(after),real_get('ReaSetSmokeCL','repair')
  end
  local _,prior_blob=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
  local prior=J.decode(prior_blob)
  local cued,reply=chart_edit('cue','cue',{section=2,time=12})
  check(reply:match('^cue|ok|')~=nil and cued.sections[2].start==12,'Live cue command confirmed')
  check(J.encode(cued.sections[2].rows)==J.encode(prior.sections[2].rows),'Cue preserves every source word and chord column')
  local allrows,keys=J.array(),J.array()
  for si,s in ipairs(cued.sections)do for ri,row in ipairs(s.rows)do
    allrows[#allrows+1]=row;keys[#keys+1]=row.id or ('legacy-'..si..'-'..ri)
  end end
  local joined,layout_reply=chart_edit('layout','layout',{sections={{label='Complete chart',start=0,rows=keys}}})
  check(layout_reply:match('^layout|ok|')~=nil and #joined.sections==1,'Live full-chart layout command confirmed')
  check(J.encode(joined.sections[1].rows)==J.encode(allrows),'Joining sections preserves authored rows exactly')
  local _,rejected=chart_edit('old-layout','layout',{sections={{label='Stale',start=0,rows=keys}}},prior.revision)
  check(rejected:match('^old%-layout|error|')~=nil,'Stale full-chart editor rejected')
  check(apply('late-restore',{restore=folder..'/two/before.json',expected=folder..'/two/after.json'}).status=='error','Rollback preserves subsequent section edits')
  local old_tick,old_exit=tick,bridge_exit
  real_dofile(root..'/Requirements/ReaSet_ChordsLyrics.lua')
  local owner,meta=real_get('ReaSetSmokeCL','instance'),real_get('ReaSetSmokeCL','meta')
  old_tick();old_exit()
  check(owner==real_get('ReaSetSmokeCL','instance') and meta==real_get('ReaSetSmokeCL','meta') and tick~=old_tick,'Duplicate publisher yields without clearing the new instance')
end)
-- Always restore the original tab, including on a failed assertion.
local cleaned,cleanup_error=pcall(function()
  if scratch and scratch~=original and reaper.ValidatePtr(scratch,'ReaProject*')then
    reaper.SelectProjectInstance(scratch)
    reaper.Main_SaveProjectEx(scratch,folder..'/scratch.RPP',8)
    reaper.Main_OnCommand(40860,0)
  end
end)
reaper.SelectProjectInstance(original)
local unchanged=reaper.GetProjectStateChangeCount(original)==original_changes and reaper.GetCursorPosition()==original_cursor
write(folder..'/result.json',J.encode({ok=ok and cleaned and unchanged,error=tostring(why or cleanup_error or ''),original_unchanged=unchanged,checks=checks}))
'''
    source=source.replace('ROOT',json.dumps(ROOT.as_posix())).replace('FOLDER',json.dumps(folder.as_posix()))
    script=folder/'verify.lua';script.write_text(source,encoding='utf-8')
    subprocess.Popen(['C:/Program Files/REAPER (x64)/reaper.exe','-nonewinst',str(script)])
    result=folder/'result.json'
    for _ in range(450):
        if result.exists():break
        time.sleep(.2)
    if not result.exists():raise RuntimeError('No REAPER receipt; inspect '+str(folder))
    data=json.loads(result.read_text());print(json.dumps(data,indent=2));print('Artifacts:',folder)
    if not data['ok']:raise SystemExit(1)


if __name__=='__main__':main()
