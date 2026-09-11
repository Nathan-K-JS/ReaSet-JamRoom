"""Check native and ReaSet Play after append imports into a populated library.

Usage: python tools/verify_import_playback.py "imports/Artist - Song"
Requires stopped REAPER with a saved, populated Jam Room project and Edge.
Opens the last saved project as a disposable template; never saves the original.
Uses cached audio, the production apply action via HTTP, and real playback.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

import requests
from playwright.sync_api import sync_playwright

import jamroom_import as importer

ROOT = Path(__file__).resolve().parent.parent
WEB = 'http://127.0.0.1:8080'


def wait_file(path, timeout=30):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() > deadline:
            raise RuntimeError('Missing REAPER receipt: ' + str(path))
        time.sleep(.1)
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('song', type=Path)
    parser.add_argument('--click-library-check', action='store_true',
                        help='Use the real importer UI to add clicks to the scratch library; requires an idle importer')
    parser.add_argument('--apply-script', type=Path, default=ROOT / 'tools/jamroom_import_apply.lua',
                        help='Optional historical script for a regression control')
    args = parser.parse_args()
    source = args.song.resolve()
    cached = json.loads((source / 'job.json').read_text(encoding='utf-8'))
    session = requests.Session()
    session.trust_env = False

    def web(command):
        result = session.get(WEB + '/_/' + command, timeout=10)
        result.raise_for_status()
        return result.text

    assert web('TRANSPORT').split('\t')[1] == '0', 'Stop REAPER first'
    parent = ROOT / 'imports/.visual'
    parent.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='append-', dir=parent))
    for sub in ('tools', 'Requirements'):
        (folder / sub).mkdir()
    shutil.copy2(args.apply_script, folder / 'tools/jamroom_import_apply.lua')
    shutil.copy2(ROOT / 'Requirements/ReaSet_JSON.lua', folder / 'Requirements')
    lua = r'''
local root,folder=ROOT,FOLDER
local J=dofile(root..'/Requirements/ReaSet_JSON.lua')
local original,path=reaper.EnumProjects(-1,'')
local importer_state=reaper.GetExtState('ReaSetJR','importer')
local cursor=reaper.GetCursorPosition()
local count=reaper.GetProjectStateChangeCount(original)
local function snapshot(project)
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
    parts[#parts+1]=J.encode({region,a,b,name,id,color});i=i+1
  end
  return table.concat(parts,'\n')
end
local before=snapshot(original)
local function write(name,data)
  local f=assert(io.open(folder..'/'..name,'w'));f:write(J.encode(data));f:close()
end
local scratch,cmd
reaper.atexit(function()
  if scratch and reaper.ValidatePtr(scratch,'ReaProject*') then
    reaper.SelectProjectInstance(scratch);reaper.OnStopButton()
    reaper.Main_SaveProjectEx(scratch,folder..'/scratch.RPP',8)
    reaper.Main_OnCommand(40860,0)
  end
  if cmd then reaper.AddRemoveReaScript(false,0,folder..'/tools/jamroom_import_apply.lua',true)end
  reaper.SelectProjectInstance(original)
  reaper.SetExtState('ReaSetJR','importer',importer_state,false)
  write('cleanup.json',{original_unchanged=before==snapshot(original) and cursor==reaper.GetCursorPosition(),
    state_counter_unchanged=count==reaper.GetProjectStateChangeCount(original)})
end)
local function run()
  assert(reaper.GetPlayState()==0 and path~='','A stopped, saved library is required')
  reaper.Main_OnCommand(40859,0);scratch=reaper.EnumProjects(-1,'')
  assert(scratch~=original)
  reaper.Main_openProject('template:'..path)
  assert(reaper.CountMediaItems(0)>0,'Use a populated saved library')
  reaper.SetProjExtState(0,'ReaSet','projectId','append-'..tostring(math.floor(reaper.time_precise()*1000)))
  reaper.SetMediaTrackInfo_Value(reaper.GetMasterTrack(0),'B_MUTE',1)
  local existing
  for i=0,reaper.CountProjectMarkers(0)-1 do
    local ok,region,a,b=reaper.EnumProjectMarkers3(0,i)
    if ok>0 and region and b-a>20 then existing=a+10 end
  end
  assert(existing,'A song region longer than 20 seconds is required')
  cmd=reaper.AddRemoveReaScript(true,0,folder..'/tools/jamroom_import_apply.lua',true)
  assert(cmd~=0)
  write('ready.json',{command='_'..reaper.ReverseNamedCommandLookup(cmd),existing=existing})
  local deadline=reaper.time_precise()+300
  local pending
  local function tick()
    local finish=io.open(folder..'/finish','r')
    if finish then finish:close();return end
    if reaper.time_precise()>deadline then return end
    if pending then
      if reaper.time_precise()-pending.started>=1.2 then
        local result={position=reaper.GetPlayPosition(),state=reaper.GetPlayState(),
          expected=pending.position,tracks=reaper.CountTracks(0)}
        reaper.OnStopButton();pending=nil;write('response.json',result)
      end
    else
      local f=io.open(folder..'/request.json','r')
      if f then
        local request=J.decode(f:read('*a'));f:close();os.remove(folder..'/request.json')
        reaper.SetEditCurPos(request.position,false,true);reaper.OnPlayButton()
        pending={position=request.position,started=reaper.time_precise()}
      end
    end
    reaper.defer(tick)
  end
  reaper.defer(tick)
end
local ok,why=pcall(run)
if not ok then write('error.json',{error=tostring(why)})end
'''.replace('ROOT', json.dumps(ROOT.as_posix())).replace('FOLDER', json.dumps(folder.as_posix()))
    script = folder / 'probe.lua'
    script.write_text(lua, encoding='utf-8')
    print('Artifacts:', folder, flush=True)
    subprocess.Popen([str(importer.load_config(None)['reaper_exe']), '-nonewinst', str(script)])
    checks = []

    def probe(label, position):
        (folder / 'response.json').unlink(missing_ok=True)
        pending = folder / 'request.tmp'
        pending.write_text(json.dumps({'position': position}))
        pending.replace(folder / 'request.json')
        result = wait_file(folder / 'response.json')
        result['check'] = label
        checks.append(result)
        (folder / 'checks.json').write_text(json.dumps(checks, indent=2))
        assert result['state'] == 1 and position + .15 < result['position'] < position + 5, result

    try:
        ready = wait_file(folder / 'ready.json')
        probe('native before import', ready['existing'])
        for n in (1, 2):
            job = copy.deepcopy(cached)
            job['region_name'] = 'Append playback check ' + str(n)
            # First pass adds named buses; second pass reuses those buses.
            for slot in job.get('slots', []):
                slot['label'] += ' playback check'
            importer.write_reaper_job(job, folder)
            generated = folder / 'job_for_reaper.lua'
            content = generated.read_text(encoding='utf-8')
            for slot in job.get('slots', []):
                assert (source / slot['file']).is_file(), slot['file']
                content = content.replace(importer.lua_quote(folder.as_posix() + '/' + slot['file']),
                                          importer.lua_quote((source / slot['file']).as_posix()))
            generated.write_text(content, encoding='utf-8')
            (folder / 'applied.txt').unlink(missing_ok=True)
            (folder / 'tools/jamroom_pending_job.txt').write_text(folder.as_posix())
            web(ready['command'])
            receipt = (folder / 'applied.txt').read_text(encoding='utf-8')
            position = float(re.search(r' pos=([\d.]+)', receipt)[1]) + 30
            assert 'stems=0' not in receipt and 'SKIPPED:' not in receipt, receipt
            probe('native existing song after import ' + str(n), ready['existing'])
            probe('native appended song ' + str(n), position)
        # A failed source can still create a bus before the import aborts.
        missing = importer.lua_quote((folder / 'missing.wav').as_posix())
        (folder / 'job_for_reaper.lua').write_text(
            'return {region_name="Aborted playback check",duration=0,slots={'
            '{slot="GTR1",label="Aborted playback check",file=' + missing + '}}}')
        (folder / 'applied.txt').unlink()
        (folder / 'tools/jamroom_pending_job.txt').write_text(folder.as_posix())
        web(ready['command'])
        assert not (folder / 'applied.txt').exists(), 'Broken source was reported as imported'
        probe('native after aborted import', position)
        with sync_playwright() as pw:
            edge = Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe'
            browser = pw.chromium.launch(executable_path=str(edge), headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1000})
            page.goto(WEB + '/ReaSet.html')
            page.wait_for_function('t=>g_stableId&&g_stableId.startsWith("append-")&&initialized&&displayList.some(r=>r.start<=t&&r.end>t)', arg=position)
            # Let the initial region-load cue finish before choosing our target.
            page.wait_for_timeout(500)
            web('SET/POS/' + str(position))
            page.wait_for_function('t=>Math.abs(currentPos-t)<.1', arg=position)
            page.locator('#main-play-btn').click()
            page.wait_for_function('t=>currentPos>t+.5&&currentPos<t+5', arg=position, timeout=8000)
            state = web('TRANSPORT').split('\t')
            assert state[1] == '1' and position + .5 < float(state[2]) < position + 5, state
            checks.append({'check':'ReaSet Play after imports','expected':position,'position':float(state[2]),'state':1})
            page.screenshot(path=str(folder / 'reaset-playing.png'))
            web('1016')
            if args.click_library_check:
                importer_url='http://127.0.0.1:8765'
                status=session.get(importer_url+'/api/status',timeout=5).json()
                assert status['state']=='idle','Finish the active import first'
                listing=session.get(importer_url+'/api/updates',timeout=10).json()
                ids=[s['id'] for s in listing['songs'] if s['click_eligible']]
                assert ids,'The scratch library needs at least one missing click'
                command=';'.join('GET/PROJEXTSTATE/ReaSetSong/song:'+str(i)+':document' for i in ids)
                chart_before=web(command)
                updates=browser.new_page(viewport={'width':1200,'height':1000})
                updates.goto(importer_url+'/#updates=1')
                updates.locator('#updateMode').select_option('clicks')
                updates.locator('#updateWholeLibrary').click()
                updates.wait_for_function('updateBatch&&updateBatch.status==="complete"',timeout=180000)
                batch=updates.evaluate('updateBatch')
                assert sorted(s['id'] for s in batch['songs'])==sorted(ids),batch
                assert all(s['status']=='done' for s in batch['songs']),batch
                assert web(command)==chart_before,'Click-only batch changed chart documents'
                listing=session.get(importer_url+'/api/updates',timeout=10).json()
                assert all(s['click_current'] for s in listing['songs'] if s['id'] in ids)
                updates.screenshot(path=str(folder/'click-library.png'),full_page=True)
                (folder/'click-library.json').write_text(json.dumps(batch,indent=2))
                checks.append({'check':'Whole-library click-only update preserves charts','songs':len(ids)})
                updates.close()
            browser.close()
        if args.click_library_check:
            probe('native playback after whole-library clicks',ready['existing'])
        (folder / 'checks.json').write_text(json.dumps(checks, indent=2))
        print(json.dumps(checks, indent=2))
    finally:
        (folder / 'finish').touch()
        cleanup = wait_file(folder / 'cleanup.json')
        print('Cleanup:', cleanup)
        assert cleanup['original_unchanged'] and cleanup['state_counter_unchanged'], cleanup


if __name__ == '__main__':
    main()
