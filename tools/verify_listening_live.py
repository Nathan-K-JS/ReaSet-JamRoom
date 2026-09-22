"""Opt-in: isolated listening render plus unchanged live REAPER project checks.

Creates synthetic mono/stereo inputs, backing and click in a disposable tab.
Does not use the room's hardware inputs or modify the loaded library.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import wave

import numpy as np
import requests

import jamroom_listening as listening

ROOT = Path(__file__).resolve().parent.parent


def main():
    folder = Path(tempfile.mkdtemp(prefix='reaset-listening-'))
    t = np.arange(48000 * 6) / 48000
    for name, freqs in [('voice', [440]), ('harmony', [990]), ('band', [550, 660]), ('backing', [770]), ('click', [1800])]:
        values = np.array([np.sin(2 * np.pi * f * t) * .06 for f in freqs]).T
        with wave.open(str(folder / (name + '.wav')), 'wb') as f:
            f.setparams((len(freqs), 2, 48000, 0, 'NONE', 'not compressed'))
            f.writeframes((values * 32767).astype('<i2').tobytes())
    source = r'''
local root,folder=ROOT,FOLDER
local M=dofile(root..'/Requirements/ReaSet_RecordingCore.lua')
dofile(root..'/Requirements/ReaSet_RecordingExport.lua')(M)
local original=reaper.EnumProjects(-1,'');local changes=reaper.GetProjectStateChangeCount(original);local cursor=reaper.GetCursorPosition()
local scratch
local ok,why=xpcall(function()
assert(reaper.GetPlayState()==0,'Stop REAPER before this test')
reaper.Main_OnCommand(40859,0);scratch=reaper.EnumProjects(-1,'')
reaper.Main_SaveProjectEx(0,folder..'/scratch.RPP',8)
reaper.SetProjExtState(0,'ReaSet','projectId','listening-proof-'..M.guid())
reaper.AddProjectMarker2(0,true,10,14,'Phone listening proof',1,0)
local function item(tr,file,rec)
  local it=reaper.AddMediaItemToTrack(tr);local tk=reaper.AddTakeToMediaItem(it)
  reaper.SetMediaItemTake_Source(tk,assert(reaper.PCM_Source_CreateFromFile(folder..'/'..file..'.wav')))
  reaper.SetMediaItemInfo_Value(it,'D_POSITION',10);reaper.SetMediaItemInfo_Value(it,'D_LENGTH',4)
  reaper.SetMediaItemInfo_Value(it,'C_BEATATTACHMODE',0)
  if rec then reaper.SetMediaItemTakeInfo_Value(tk,'D_PLAYRATE',1/.8)end
  return it
end
for i,name in ipairs({'[JR:GTR1] Backing','[JR:CLICK] Click'})do
  reaper.InsertTrackAtIndex(i-1,false);local tr=reaper.GetTrack(0,i-1)
  reaper.GetSetMediaTrackInfo_String(tr,'P_NAME',name,true);item(tr,i==1 and 'backing' or 'click')
end
local core=M.new();core:setup();local song=M.P.songs()[1]
local sf=core.root..'/session';reaper.RecursiveCreateDirectory(sf,0)
local s={id='session',song=song,folder=sf,created='Test',rate=.8,semis=0,pitches={},takes=M.J.array()}
local take={id='take',number=1,status='kept',duration=4,inputs={'1','9'},items=M.J.array()}
core.db.sessions={s};s.takes={take};reaper.CSurf_OnPlayRateChange(.8)
reaper.Main_SaveProjectEx(0,sf..'/backing.RPP',0)
for i,id in ipairs({'1','9'})do
 local it=item(M.tracks()[id],i==1 and 'voice' or 'band',true)
 M.ext(it,'ReaSetRec','session/take');reaper.SetMediaItemInfo_Value(it,'B_MUTE',1)
 local _,guid=reaper.GetSetMediaItemInfo_String(it,'GUID','',false);local _,chunk=reaper.GetItemStateChunk(it,'',false)
 take.items[#take.items+1]={guid=guid,track=id,chunk=chunk}
end
M.parts(core,s,take)
core:save(true)
local before=reaper.GetProjectStateChangeCount(0)
M.make_listening(core,{session=s.id,take=take.id,backing=true,nonce='with-backing'})
assert(reaper.CountTracks(0)==19 and reaper.GetPlayState()==0,'Snapshot altered transport or tracks')
M.make_listening(core,{session=s.id,take=take.id,backing=false,nonce='without-backing'})
core:review(s.id,take.id);take.mix[take.dest['9']].muted=true;core:save(false)
M.make_listening(core,{session=s.id,take=take.id,backing=false,nonce='only-voice'})
take.mix[take.dest['9']].muted=false;take.mix[take.dest['1']].gain=.25
M.make_listening(core,{session=s.id,take=take.id,backing=false,nonce='balanced-parts'})
local harmony={id='harmony',number=2,status='kept',duration=4,inputs={'1'},items=M.J.array()}
M.parts(core,s,harmony,take);s.takes[#s.takes+1]=harmony
local it=item(M.tracks()[harmony.dest['1']],'harmony',true)
M.ext(it,'ReaSetRec','session/harmony');reaper.SetMediaItemInfo_Value(it,'B_MUTE',1)
local _,guid=reaper.GetSetMediaItemInfo_String(it,'GUID','',false);local _,chunk=reaper.GetItemStateChunk(it,'',false)
harmony.items[1]={guid=guid,track=harmony.dest['1'],chunk=chunk}
core:save(true);core:review(s.id,harmony.id)
M.make_listening(core,{session=s.id,take=harmony.id,backing=false,nonce='overdub-mix'})
M.export(core,s)
M.make_listening(core,{session=s.id,take=take.id,backing=true,nonce='after-export'})
M.write(folder..'/fixture.json',M.J.encode({root=core.root..'/Listening',project=core.id,original_changes=changes,original_cursor=cursor}))
end,debug.traceback)
if scratch and reaper.ValidatePtr(scratch,'ReaProject*')then reaper.SelectProjectInstance(scratch);reaper.Main_SaveProjectEx(0,folder..'/scratch.RPP',8);reaper.Main_OnCommand(40860,0)end
reaper.SelectProjectInstance(original)
local unchanged=reaper.GetProjectStateChangeCount(original)==changes and reaper.GetCursorPosition()==cursor
M.write(folder..'/setup-result.json',M.J.encode({ok=ok and unchanged,error=tostring(why),original_unchanged=unchanged}))
'''.replace('ROOT', json.dumps(ROOT.as_posix())).replace('FOLDER', json.dumps(folder.as_posix()))
    script = folder / 'prepare.lua'; script.write_text(source, encoding='utf-8')
    subprocess.Popen(['C:/Program Files/REAPER (x64)/reaper.exe', '-nonewinst', str(script)])
    result = folder / 'setup-result.json'
    for _ in range(200):
        if result.exists(): break
        time.sleep(.2)
    if not result.exists(): raise RuntimeError('No REAPER result: ' + str(folder))
    data = json.loads(result.read_text(encoding='utf-8'))
    print('Setup:', data, 'Artifacts:', folder, flush=True)
    assert data['ok'], data
    fixture = json.loads((folder / 'fixture.json').read_text(encoding='utf-8'))
    service = listening.Listening(lambda: {}, folder / 'service')
    service.data['roots'][fixture['project']] = fixture['root']
    service.discover()
    before = requests.get('http://localhost:8080/_/TRANSPORT', timeout=5).text
    ratios={}
    for key in service.data['jobs']:
        service.process(key)
        row = service.data['jobs'][key]
        assert row['state'] == 'ready', row
        rendered = Path(row['folder']) / 'mix.mp3'
        assert set(row['files']) == {'mp3'} and not (Path(row['folder']) / 'mix.wav').exists()
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(rendered), '-f', 'f32le', '-'], capture_output=True, check=True).stdout
        audio = np.frombuffer(raw, dtype='<f4').reshape(-1, 2)
        # Original stems keep pitch; recorded inputs compensate master playrate.
        def power(freq, channel=0):
            sample = audio[24000:120000, channel]; axis = np.arange(len(sample))/48000
            return abs(np.sum(sample * np.exp(-2j*np.pi*freq*axis)))/len(sample)
        ratios[row['id']]=power(440)/max(power(550),1e-10)
        if row['id']=='overdub-mix': assert power(990)>.005, 'Same-input harmony missing'
        assert power(440) > .003, (row['id'], 'voice missing')
        assert power(1800) < .001, (row['id'], 'click leaked')
        if row['id'] == 'only-voice': assert power(550) < .001
        else: assert power(550, 0) > .005 and power(660, 1) > .005
        if row['id'] in ('with-backing', 'after-export'): assert power(770) > .005
        else: assert power(770) < .001
        print(row['id'], 'PASS', row['duration'], 'seconds', row['files'], flush=True)
    assert abs(ratios['balanced-parts']/ratios['without-backing']-.25)<.03, ratios
    assert abs(ratios['overdub-mix']/ratios['without-backing']-.25)<.03, ratios
    print('Saved part levels and same-input harmony verified in rendered MP3 audio.',flush=True)
    after = requests.get('http://localhost:8080/_/TRANSPORT', timeout=5).text
    assert before == after, (before, after)
    print('Original transport unchanged throughout all worker renders.', flush=True)


if __name__ == '__main__': main()
