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
import jamroom_click as click

ROOT=Path(__file__).resolve().parent.parent


def main():
    folder=Path(tempfile.mkdtemp(prefix='reaset-live-'))
    click.render(folder/'click.wav',[.25+i*.5 for i in range(120)],60)
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
  reaper.InsertTrackAtIndex(reaper.CountTracks(0),false)
  reaper.GetSetMediaTrackInfo_String(reaper.GetTrack(0,reaper.CountTracks(0)-1),'P_NAME','PB CLICK',true)
  local _,chart_before_click=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
  check(apply('click',{lyrics=false,chords=false,document=false,click={file=folder..'/click.wav',revision='test-click',muted=true}}).status=='ok','Click-only transaction applies')
  local C=real_dofile(root..'/Requirements/ReaSet_Click.lua')
  local ct=C.track(false);check(ct and reaper.CountTrackMediaItems(ct)==1,'One click item on CLICK bus')
  local ci=reaper.GetTrackMediaItem(ct,0)
  check(reaper.GetMediaItemInfo_Value(ci,'B_MUTE')==1,'Flagged click installs muted')
  check(C.owned(ci) and math.abs(reaper.GetMediaItemInfo_Value(ci,'D_LENGTH')-60)<.001,'Click item owns full recording duration')
  local _,chart_after_click=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
  check(chart_before_click==chart_after_click,'Click-only update preserves saved chart exactly')
  check(apply('click-again',{lyrics=false,chords=false,document=false,click={file=folder..'/click.wav',revision='test-click'}}).status=='ok' and reaper.CountTrackMediaItems(ct)==1,'Click replacement does not duplicate clicks')
  check(apply('click-restore',{restore=folder..'/click/before.json',expected=folder..'/click-again/after.json'}).status=='ok' and reaper.CountTrackMediaItems(ct)==0,'Click backup restores no-click state')
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
  -- Exercise click enable through the production bridge, including a muted
  -- item under an unmuted PB bus (the native TRACK state misses this).
  local jr_set,jr_get=reaper.SetExtState,reaper.GetExtState
  reaper.SetExtState=function(sec,key,value,persist)real_set(sec=='ReaSetJR' and 'ReaSetSmokeJR' or sec,key,value,persist)end
  reaper.GetExtState=function(sec,key)return real_get(sec=='ReaSetJR' and 'ReaSetSmokeJR' or sec,key)end
  local click_item=C.install(ct,reaper.PCM_Source_CreateFromFile(folder..'/click.wav'),0,60,'Smoke',true)
  local later_item=C.install(ct,reaper.PCM_Source_CreateFromFile(folder..'/click.wav'),80,60,'Later',true)
  real_dofile(root..'/Requirements/ReaSet_JamRoom.lua');tick()
  local function jr_payload()
    local n=tonumber(real_get('ReaSetSmokeJR','meta'):match(':(%d+)$'))
    local pieces={};for i=0,n-1 do pieces[#pieces+1]=real_get('ReaSetSmokeJR','d'..i):match('^[^:]+:(.*)$')end
    return J.decode(table.concat(pieces))
  end
  local control=jr_payload().songs[tostring(id)].controls[1]
  check(control.clickBlocked,'Bridge reports item mute under enabled bus')
  real_set('ReaSetSmokeJR','clickWant',control.clickKey..'|0',false);tick();tick()
  check(reaper.GetMediaItemInfo_Value(click_item,'B_MUTE')==0,'Click enable clears current song item mute')
  check(reaper.GetMediaItemInfo_Value(later_item,'B_MUTE')==1,'Click enable preserves other song item')
  check(not jr_payload().songs[tostring(id)].controls[1].clickBlocked,'Bridge confirms click enabled')
  bridge_exit()
  reaper.SetExtState,reaper.GetExtState=jr_set,jr_get
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
  local shifted,shift_reply=chart_edit('shift','offset',{seconds=-1.5})
  check(shift_reply:match('^shift|ok|')~=nil and shifted.timing_offset==-1.5,'Whole-song offset saved through live bridge')
  check(J.encode(shifted.sections)==J.encode(cued.sections),'Whole-song offset preserves individual page cues')
  local allrows,keys=J.array(),J.array()
  for si,s in ipairs(cued.sections)do for ri,row in ipairs(s.rows)do
    allrows[#allrows+1]=row;keys[#keys+1]=row.id or ('legacy-'..si..'-'..ri)
  end end
  local joined,layout_reply=chart_edit('layout','layout',{sections={{label='Complete chart',start=0,rows=keys}}})
  check(layout_reply:match('^layout|ok|')~=nil and #joined.sections==1,'Live full-chart layout command confirmed')
  check(J.encode(joined.sections[1].rows)==J.encode(allrows),'Joining sections preserves authored rows exactly')
  local _,rejected=chart_edit('old-layout','layout',{sections={{label='Stale',start=0,rows=keys}}},prior.revision)
  check(rejected:match('^old%-layout|error|')~=nil,'Stale full-chart editor rejected')
  local authored=J.decode(J.encode(joined))
  authored.sections[1].rows[1].text='New original words from authoring'
  authored.sections[1].rows[1].chord_line='Dm7     G/B'
  authored.sections[1].rows[1].anchors=J.array({{symbol='Dm7',offset=0,width=3},{symbol='G/B',offset=8,width=3}})
  local written,author_reply=chart_edit('author','author',authored)
  check(author_reply:match('^author|ok|')~=nil,'Authored words accepted through chunked native bridge')
  check(written.sections[1].rows[1].text=='New original words from authoring','Authored words installed')
  check(written.sections[1].rows[1].anchors[2].offset==8,'Authored chord columns preserved')
  local _,previous=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':previous')
  check(J.decode(previous).revision==joined.revision,'Previous native chart is recoverable')
  local _,stale_author=chart_edit('stale-author','author',authored,joined.revision)
  check(stale_author:match('^stale%-author|error|')~=nil,'Stale authored chart rejected')
  local undo_label=reaper.Undo_CanUndo2(0)
  local undo_result=reaper.Undo_DoUndo2(0)
  tick()
  local _,undo_blob=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
  check(J.decode(undo_blob).revision==joined.revision,'Single native undo restores chart content '..tostring(undo_label)..' / '..tostring(undo_result)..' / '..tostring(J.decode(undo_blob).revision)..' expected '..tostring(joined.revision))
  local malformed=J.decode(J.encode(authored));malformed.sections[1].rows[1].anchors[1].offset=-1
  local _,bad_author=chart_edit('bad-author','author',malformed)
  check(bad_author:match('^bad%-author|error|')~=nil,'Invalid authored chord position rejected')
  check(apply('late-restore',{restore=folder..'/two/before.json',expected=folder..'/two/after.json'}).status=='error','Rollback preserves subsequent section edits')
  local old_tick,old_exit=tick,bridge_exit
  real_dofile(root..'/Requirements/ReaSet_ChordsLyrics.lua')
  local owner,meta=real_get('ReaSetSmokeCL','instance'),real_get('ReaSetSmokeCL','meta')
  old_tick();old_exit()
  check(owner==real_get('ReaSetSmokeCL','instance') and meta==real_get('ReaSetSmokeCL','meta') and tick~=old_tick,'Duplicate publisher yields without clearing the new instance')

  -- Native item-level matching, with durable transaction/rollback semantics.
  local P=real_dofile(root..'/Requirements/ReaSet_Playback.lua')
  local backing={}
  for _,slot in ipairs({'BASS','KEYS'})do
    reaper.InsertTrackAtIndex(reaper.CountTracks(0),false)
    local tr=reaper.GetTrack(0,reaper.CountTracks(0)-1)
    reaper.GetSetMediaTrackInfo_String(tr,'P_NAME','[JR:'..slot..'] '..slot,true)
    local it=reaper.AddMediaItemToTrack(tr);local tk=reaper.AddTakeToMediaItem(it)
    reaper.SetMediaItemTake_Source(tk,reaper.PCM_Source_CreateFromFile(folder..'/click.wav'))
    reaper.SetMediaItemInfo_Value(it,'D_POSITION',0);reaper.SetMediaItemInfo_Value(it,'D_LENGTH',60)
    backing[#backing+1]=it
  end
  reaper.SetMediaItemInfo_Value(backing[2],'D_VOL',.5)
  local song=P.songs()[1]
  local _,chart_before=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
  local click_gain=reaper.GetMediaItemInfo_Value(click_item,'D_VOL')
  local report={status='measured',revision='volume-one',gain=.4,files={folder..'/click.wav',folder..'/click.wav'}}
  local function levels(op,extra)
    local body={document=false,lyrics=false,chords=false,level=report}
    for k,v in pairs(extra or {})do body[k]=v end
    return apply(op,body)
  end
  check(levels('levels-one').status=='ok','Volume transaction applies to actual backing items')
  check(math.abs(reaper.GetMediaItemInfo_Value(backing[1],'D_VOL')-.4)<.00001 and math.abs(reaper.GetMediaItemInfo_Value(backing[2],'D_VOL')-.2)<.00001,'Matching preserves relative stem balance')
  check(levels('levels-one').status=='ok' and math.abs(P.gain(song)-.4)<.00001,'Lost level receipt retry does not compound gain')
  local _,chart_after=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
  check(chart_before==chart_after and reaper.GetMediaItemInfo_Value(click_item,'D_VOL')==click_gain,'Level-only update preserves chart and click')
  P.set(song,.7);report.gain=.3;report.revision='volume-two'
  check(levels('levels-two').status=='ok' and math.abs(P.gain(song)-.7)<.00001,'Manual playback adjustment survives re-analysis')
  check(P.level(song).manual and math.abs(P.level(song).gain-.3)<.00001,'New suggestion is saved beside manual level')
  report.replace=true
  check(levels('levels-force').status=='ok' and math.abs(P.gain(song)-.3)<.00001,'Explicit replacement applies matched suggestion')
  check(levels('levels-restore',{level=false,restore=folder..'/levels-force/before.json',expected=folder..'/levels-force/after.json'}).status=='ok' and math.abs(P.gain(song)-.7)<.00001,'Restore recovers previous manual volume and mode')
  P.set(song,.6)
  check(levels('levels-stale-restore',{level=false,restore=folder..'/levels-two/before.json',expected=folder..'/levels-two/after.json'}).status=='error','Restore cannot overwrite a later manual level')
  report.gain=2
  check(levels('levels-invalid').status=='error' and math.abs(P.gain(song)-.6)<.00001,'Invalid level rolls back without changing manual volume')
  report.gain=.3
  report.files={folder..'/missing.wav'}
  check(levels('levels-source-mismatch').status=='error' and math.abs(P.gain(song)-.6)<.00001,'Changed backing files prevent applying stale matching')
  reaper.SetEditCurPos(10,false,false)
  local persisted,persist_reply=chart_edit('persist-author','author',authored)
  check(persist_reply:match('^persist%-author|ok|')~=nil,'Final authored chart saved for reopen check')
  reaper.Main_SaveProjectEx(scratch,folder..'/authored.RPP',8)
  reaper.Main_OnCommand(40859,0)
  local reopened=reaper.EnumProjects(-1,'')
  reaper.Main_openProject(folder..'/authored.RPP')
  local _,reopened_blob=reaper.GetProjExtState(0,'ReaSetSong','song:'..id..':document')
  local decoded,reopened_doc=pcall(J.decode,reopened_blob)
  reaper.Main_SaveProjectEx(reopened,folder..'/reopened.RPP',8)
  reaper.Main_OnCommand(40860,0);reaper.SelectProjectInstance(scratch)
  check(decoded and reopened_doc.sections[1].rows[1].text=='New original words from authoring','Authored chart survives saving and reopening the project')
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
