"""Import a cached song into a scratch REAPER tab and photograph the live UI.

Requires stopped REAPER, its web interface, Playwright and Microsoft Edge.
Usage: python tools/verify_song_visual.py [path/to/cached/song]
Add --playback-check to verify actual playback crosses saved section cues.
Audio stays in its original location. Evidence is saved under imports/.visual/.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import requests
from playwright.sync_api import sync_playwright
import jamroom_import as importer

ROOT = Path(__file__).resolve().parent.parent
WEB = 'http://127.0.0.1:8080'


def wait_file(path, timeout=45):
    until = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() > until:
            raise RuntimeError('Missing REAPER receipt: ' + str(path))
        time.sleep(.2)


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'imports/Fleetwood Mac - Dreams').resolve()
    session = requests.Session()
    session.trust_env = False
    transport = session.get(WEB + '/_/TRANSPORT', timeout=5).text.split('\t')
    assert transport[1] == '0', 'Stop REAPER before running this check'
    parent = ROOT / 'imports/.visual'
    parent.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='song-', dir=parent))
    job = json.loads((source / 'job.json').read_text(encoding='utf-8'))
    for slot in job.get('slots', []):
        assert (source / slot['file']).is_file(), slot['file']
    importer.write_reaper_job(job, folder)
    generated = folder / 'job_for_reaper.lua'
    content = generated.read_text(encoding='utf-8')
    for slot in job.get('slots', []):
        content = content.replace(importer.lua_quote(folder.as_posix() + '/' + slot['file']),
                                  importer.lua_quote((source / slot['file']).as_posix()))
    generated.write_text(content, encoding='utf-8')
    (folder / 'tools').mkdir()
    (folder / 'Requirements').mkdir()
    shutil.copy2(ROOT / 'tools/jamroom_import_apply.lua', folder / 'tools')
    shutil.copy2(ROOT / 'Requirements/ReaSet_JSON.lua', folder / 'Requirements')
    (folder / 'tools/jamroom_pending_job.txt').write_text(folder.as_posix(), encoding='utf-8')
    lua = r'''
local root,folder=ROOT,FOLDER
local J=dofile(root..'/Requirements/ReaSet_JSON.lua')
local original=reaper.EnumProjects(-1,'')
local function song_snapshot(project)
  local parts={}
  for i=-1,reaper.CountTracks(project)-1 do
    local track=i<0 and reaper.GetMasterTrack(project) or reaper.GetTrack(project,i)
    local ok,chunk=reaper.GetTrackStateChunk(track,'',false);assert(ok)
    parts[#parts+1]=chunk
  end
  local i=0
  while true do
    local ok,region,a,b,name,id,color=reaper.EnumProjectMarkers3(project,i)
    if ok==0 then break end
    parts[#parts+1]=J.encode({region=region,start=a,finish=b,name=name,id=id,color=color});i=i+1
  end
  for _,section in ipairs({'ReaSetSong','ReaSetCLRepair','ReaSet'}) do
    local entries={};local i=0
    while true do
      local ok,key,value=reaper.EnumProjExtState(project,section,i)
      if not ok then break end
      entries[#entries+1]=key..'='..value;i=i+1
    end
    table.sort(entries);parts[#parts+1]=table.concat(entries,'\n')
  end
  return table.concat(parts,'\n---\n')
end
local original_snapshot=song_snapshot(original)
local count=reaper.GetProjectStateChangeCount(original)
local cursor=reaper.GetCursorPosition()
local scratch,closed=nil,false
local function write(name,data)
  local f=assert(io.open(folder..'/'..name,'w'));f:write(J.encode(data));f:close()
end
local function cleanup()
  if closed then return end;closed=true
  if scratch and reaper.ValidatePtr(scratch,'ReaProject*')then
    reaper.SelectProjectInstance(scratch)
    reaper.OnStopButton()
    reaper.Main_SaveProjectEx(scratch,folder..'/scratch.RPP',8)
    reaper.Main_OnCommand(40860,0)
  end
  reaper.SelectProjectInstance(original)
  write('cleanup.json',{original_unchanged=song_snapshot(original)==original_snapshot and reaper.GetCursorPosition()==cursor,
    state_counter_unchanged=reaper.GetProjectStateChangeCount(original)==count})
end
local exit_callback
reaper.atexit(function()if exit_callback then exit_callback()end;cleanup()end)
local actual_defer=reaper.defer
local deadline=reaper.time_precise()+180
reaper.defer=function(fn)
  actual_defer(function()
    local f=io.open(folder..'/finish','r')
    if f then f:close()end
    if f or reaper.time_precise()>deadline then
      if exit_callback then exit_callback();exit_callback=nil end
      cleanup();return
    end
    local ok,why=pcall(fn)
    if not ok then write('error.json',{error=tostring(why)});cleanup()end
  end)
end
local ok,why=pcall(function()
  assert(reaper.GetPlayState()==0,'Playback must be stopped')
  assert(reaper.kbd_getTextFromCmd(40859,0)=='New project tab')
  assert(reaper.kbd_getTextFromCmd(40860,0)=='Close current project tab')
  reaper.Main_OnCommand(40859,0);scratch=reaper.EnumProjects(-1,'')
  assert(scratch~=original and reaper.CountTracks(0)==0,'Expected empty scratch tab')
  reaper.SetProjExtState(0,'ReaSet','projectId','visual-'..tostring(math.floor(reaper.time_precise())))
  for _,name in ipairs({'PB DRUMS','PB PERC/FX','PB BASS','PB GTR 1','PB GTR 2','PB KEYS','PB BVs','PB LEAD VOX','PB CLICK','PB EXTRA'})do
    local i=reaper.CountTracks(0);reaper.InsertTrackAtIndex(i,false)
    reaper.GetSetMediaTrackInfo_String(reaper.GetTrack(0,i),'P_NAME',name,true)
  end
  reaper.SetMediaTrackInfo_Value(reaper.GetMasterTrack(0),'B_MUTE',1)
  dofile(folder..'/tools/jamroom_import_apply.lua')
  local f=assert(io.open(folder..'/applied.txt','r'),'Import did not produce a receipt');f:close()
  reaper.SetEditCurPos(0,false,false)
  write('ready.json',{tracks=reaper.CountTracks(0),items=reaper.CountMediaItems(0)})
  if reaper.GetExtState('ReaSetCL','heartbeat')=='' then
    reaper.atexit=function(fn)exit_callback=fn end
    dofile(root..'/Requirements/ReaSet_ChordsLyrics.lua')
  else
    local function tick()reaper.defer(tick)end;tick()
  end
end)
if not ok then write('error.json',{error=tostring(why)});cleanup()end
'''.replace('ROOT', json.dumps(ROOT.as_posix())).replace('FOLDER', json.dumps(folder.as_posix()))
    script = folder / 'visual.lua'
    script.write_text(lua, encoding='utf-8')
    print('Artifacts:', folder, flush=True)
    subprocess.Popen(['C:/Program Files/REAPER (x64)/reaper.exe', '-nonewinst', str(script)])
    errors, samples = [], []
    try:
        wait_file(folder / 'ready.json')
        with sync_playwright() as pw:
            edge = Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe'
            browser = pw.chromium.launch(executable_path=str(edge), headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: (folder / 'edit-request.txt').write_text(r.url, encoding='utf-8') if 'SET/EXTSTATE/ReaSetCL/want/' in r.url else None)
            page.goto(WEB + '/ReaSet.html')
            page.locator('#tab-btn-chords').click()
            page.locator('[data-cv="sheet"]').click()
            page.wait_for_function('g_clData && g_clData.song && g_clData.lyrics.length > 0 && clAlive()')
            times = [0, 30, 75, 140]
            for seconds in times:
                session.get(WEB + '/_/SET/POS/' + str(seconds), timeout=5).raise_for_status()
                page.wait_for_function('(t)=>Math.abs(currentPos-t)<1', arg=seconds)
                page.wait_for_timeout(700)
                assert page.locator('[data-cv="sheet"]').evaluate('(e)=>e.classList.contains("on")')
                path = folder / ('chords-lyrics-%03d.png' % seconds)
                page.screenshot(path=str(path), full_page=True)
                samples.append({'seconds':seconds,'screenshot':path.name,'text':page.locator('#chords-live').inner_text()})
            page.set_viewport_size({'width':768,'height':1024})
            page.wait_for_timeout(500)
            page.screenshot(path=str(folder / 'chords-lyrics-tablet.png'), full_page=True)
            if '--playback-check' in sys.argv:
                sections=page.evaluate('g_clData.document.sections')
                candidates=[s for s in sections[1:] if s['end']-s['start']>=3]
                targets=[]
                if candidates:
                    for section in (candidates[0], next((s for s in candidates if s['label']=='Bridge'),candidates[len(candidates)//2]),candidates[-1]):
                        if section not in targets:targets.append(section)
                checks=[]
                for section in targets:
                    start=max(0,section['start']-1.5)
                    session.get(WEB+'/_/SET/POS/'+str(start),timeout=5).raise_for_status()
                    page.evaluate('chartFollow()')
                    try:
                        session.get(WEB+'/_/1007',timeout=5).raise_for_status()
                        page.wait_for_function('t=>currentPos>=t&&currentPos<t+5',arg=section['start']+.5,timeout=8000)
                        state=session.get(WEB+'/_/TRANSPORT',timeout=5).text.split('\t')
                        label=page.get_by_role('combobox',name='Chart section').locator('option:checked').inner_text()
                        assert state[1]=='1' and label==section['label'],(state,label,section)
                        checks.append({'cue':section['start'],'section':label,'playing_position':float(state[2])})
                        page.screenshot(path=str(folder/('playing-'+str(len(checks))+'.png')))
                    finally:
                        session.get(WEB+'/_/1016',timeout=5).raise_for_status()
                (folder/'playback-following.json').write_text(json.dumps(checks,indent=2))
            if '--edit-check' in sys.argv:
                page.set_viewport_size({'width':1440,'height':1000})
                before = page.evaluate('g_clData.document')
                page.get_by_role('button', name='Edit sections', exact=True).click()
                page.get_by_role('button', name='Start section here', exact=True).first.click()
                page.screenshot(path=str(folder / 'section-editor.png'), full_page=True)
                page.get_by_role('button', name='Save sections', exact=True).click()
                page.wait_for_function('r => g_clData.document.revision !== r', arg=before['revision'])
                edited = page.evaluate('g_clData.document')
                assert len(edited['sections']) == len(before['sections']) + 1
                assert [r for s in before['sections'] for r in s['rows']] == [r for s in edited['sections'] for r in s['rows']]
                # Test a real cue tap at a stopped transport position, not a
                # synthetic browser acknowledgment or a mutation of its data.
                section = edited['sections'][1]
                target = section['start'] + min(.1, (section['end']-section['start'])/2)
                session.get(WEB + '/_/SET/POS/' + str(target), timeout=5).raise_for_status()
                page.wait_for_function('(t)=>Math.abs(currentPos-t)<.02', arg=target)
                page.get_by_role('combobox', name='Chart section').select_option('1')
                page.get_by_role('button', name='Timing', exact=True).click()
                page.get_by_role('button', name='This page starts now', exact=True).click()
                page.wait_for_function('r => g_clData.document.revision !== r', arg=edited['revision'])
                cued = page.evaluate('g_clData.document')
                assert abs(cued['sections'][1]['start']-target) < .02
                assert [r for s in edited['sections'] for r in s['rows']] == [r for s in cued['sections'] for r in s['rows']]
                page.screenshot(path=str(folder / 'cue-confirmed.png'), full_page=True)
                (folder / 'edits.json').write_text(json.dumps({'split_confirmed':True,'cue_confirmed':True,'source_rows_unchanged':True},indent=2))
            evidence = page.evaluate('({song:g_clData.song,chords:g_clData.chords.length,lyrics:g_clData.lyrics.length,bridgeAlive:clAlive(),mode:g_chordView})')
            browser.close()
        assert not errors, errors
        (folder / 'result.json').write_text(json.dumps({'live':evidence,'samples':samples,'browser_errors':errors},indent=2),encoding='utf-8')
        print(json.dumps(evidence))
        print((folder / 'applied.txt').read_text(encoding='utf-8').strip())
    finally:
        (folder / 'finish').touch()
        wait_file(folder / 'cleanup.json')
        cleanup = json.loads((folder / 'cleanup.json').read_text())
        print('Cleanup:', cleanup)
        assert cleanup['original_unchanged'], 'Original project changed; inspect cleanup evidence'


if __name__ == '__main__':
    main()
