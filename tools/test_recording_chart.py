"""Recording/chart regressions with fake REAPER and an intercepted browser."""
import json
import io
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from lupa import LuaRuntime
import test_browser as bt
import test_unified_chart as charts

ROOT = Path(__file__).resolve().parent.parent


class CountInTests(unittest.TestCase):
    def runtime(self, beats=None):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.globals().root=ROOT.as_posix()
        lua.globals().report=json.dumps({'beats':beats or [.2+i*.5 for i in range(20)]})
        lua.execute('''
J=dofile(root..'/Requirements/ReaSet_JSON.lua')
click={D_POSITION=120,D_LENGTH=30,take={D_PLAYRATE=1,D_STARTOFFS=0,source='dummy-click.wav'}}
reaper={GetActiveTake=function(it)return it.take end,
 GetMediaItemTake_Source=function(t)return t.source end,
 GetMediaSourceFileName=function(s)return s end,
 GetMediaItemTakeInfo_Value=function(t,k)return t[k]end,
 GetMediaItemInfo_Value=function(it,k)return it[k]end}
read=function()return report end
grid=dofile(root..'/Requirements/ReaSet_RecordingCountIn.lua')
song={start=120};rows={{item=click,slot='CLICK'}}
''')
        return lua

    def test_opening_click_beats_override_unrelated_tempo_and_preserve_phase(self):
        lua=self.runtime([.2+i*60/137 for i in range(20)])
        beat,phase=lua.eval('grid.grid(song,rows,read,J.decode)')
        self.assertAlmostEqual(beat,60/137)
        self.assertAlmostEqual(phase,.2)

    def test_opening_half_double_tempo_regression(self):
        # The captured opening pulse spacing, represented without song/media data.
        lua=self.runtime([.12,.5,.872,1.248,1.624,2,2.38,2.76,3.14,3.52])
        beat,phase=lua.eval('grid.grid(song,rows,read,J.decode)')
        self.assertAlmostEqual(60/beat,158.73,places=2)
        self.assertAlmostEqual(phase,.12)

    def test_trimmed_and_stretched_click_uses_item_coordinates(self):
        lua=self.runtime()
        lua.execute('click.D_POSITION=120.1;click.take.D_STARTOFFS=.7;click.take.D_PLAYRATE=1.25')
        beat,phase=lua.eval('grid.grid(song,rows,read,J.decode)')
        self.assertAlmostEqual(beat,.4)
        self.assertAlmostEqual(phase,.1)

    def test_missing_report_reads_existing_click_audio_without_writing_it(self):
        with tempfile.TemporaryDirectory(prefix='reaset-click-unit-') as folder:
            path=Path(folder)/'click.wav'
            samples=[0]*22050*6
            for i in range(12):samples[round((.2+i*.5)*22050)]=16000
            with wave.open(str(path),'wb') as out:
                out.setparams((1,2,22050,0,'NONE','not compressed'))
                out.writeframes(struct.pack('<'+'h'*len(samples),*samples))
            original=path.read_bytes()
            lua=self.runtime();lua.globals().path=path.as_posix()
            lua.execute("click.take.source=path;report=''")
            beat,phase=lua.eval('grid.grid(song,rows,read,J.decode)')
            self.assertAlmostEqual(beat,.5,places=4)
            self.assertAlmostEqual(phase,.2,places=4)
            self.assertEqual(path.read_bytes(),original)

    def test_bad_beats_do_not_supply_a_tempo(self):
        for beats in [[1,1,1],[1,2,.5],[0,5,10]]:
            with self.subTest(beats=beats):
                self.assertIsNone(self.runtime(beats).eval('grid.grid(song,rows,read,J.decode)'))

    def test_rendered_two_bar_countin_matches_click_and_boundary(self):
        lua=self.runtime()
        lua.execute('''
M={J=J,read=read,P={items=function()return rows end},arrangement=function()return {},{}end,
 owned_items=function()end,ext=function(o,k,v)if v~=nil then o[k]=v end return o[k]or''end,
 write=function(_,data) rendered=data end}
items={click};tracks={{ReaSetCountIn='1'}};click.GUID='click'
local r=reaper
r.TimeMap_GetTimeSigAtTime=function()return 4,4,87 end
r.GetProjExtState=function()return 1,'83'end
r.GetProjectLength=function()return 200 end
r.CountMediaItems=function()return #items end
r.GetMediaItem=function(_,i)return items[i+1]end
r.GetSetMediaItemInfo_String=function(it,k,v,set)if set then it[k]=v end return true,it[k]or''end
r.SetProjExtState=function()end
r.GetItemStateChunk=function()return true,''end
r.AddMediaItemToTrack=function(tr)local it={track=tr};items[#items+1]=it;return it end
r.SetItemStateChunk=function(it)it.D_POSITION=click.D_POSITION;return true end
r.genGuid=function()return 'copy'end
r.CountTakes=function()return 0 end
r.SetMediaItemInfo_Value=function(it,k,v)it[k]=v end
r.CountTracks=function()return #tracks end
r.GetTrack=function(_,i)return tracks[i+1]end
r.SetMediaTrackInfo_Value=function()end
r.SetTrackSendInfo_Value=function()end
r.AddTakeToMediaItem=function()return {}end
r.PCM_Source_CreateFromFile=function()return {}end
r.SetMediaItemTake_Source=function()end
r.TrackList_AdjustWindows=function()end;r.UpdateArrange=function()end
r.SetEditCurPos=function(pos)cursor=pos end
self={db={countin=true,active={}},audition={},save=function()end,
 click_output=function()return 0,1 end,start_native=function()started=true end}
dofile(root..'/Requirements/ReaSet_RecordingTimeline.lua')(self,M)
s={song={start=120,finish=150,name='Fixture'},folder='unused'};t={id='take',mix={}}
self:prepare_timeline(s,t)
-- Return hex to keep the Lua bridge from decoding binary PCM as UTF-8.
hex=rendered:gsub('.',function(c)return string.format('%02x',c:byte())end)
''')
        self.assertEqual(lua.eval('t.leadin'),4)
        self.assertEqual(lua.eval('self.mode'),'countin')
        with wave.open(io.BytesIO(bytes.fromhex(lua.eval('hex'))),'rb') as audio:
            sr=audio.getframerate()
            pcm=struct.unpack('<'+'h'*audio.getnframes(),audio.readframes(audio.getnframes()))
        active=[i for i,v in enumerate(pcm) if abs(v)>500]
        starts=[active[0]/sr]+[b/sr for a,b in zip(active,active[1:]) if b-a>sr*.1]
        self.assertEqual(len(starts),8)
        for i,time in enumerate(starts):self.assertAlmostEqual(time,.2+i*.5,delta=.001)
        # The next installed click pulse is at song time .2, one beat later.
        self.assertAlmostEqual(4+.2-starts[-1],.5,delta=.001)


class NativeChartBridgeTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().root=ROOT.as_posix()
        self.lua.globals().document=json.dumps(charts.document())
        self.lua.execute('''
local original=dofile
J=original(root..'/Requirements/ReaSet_JSON.lua')
dofile=function(path)
 if path:match('ReaSet_ChartUndo.lua$')then return {sync_all=function()end}end
 return original(path)
end
wire={};playstate=5;position=9996;csc=1;project='P'
wire['ReaSetRec/lock']='P'
wire['ReaSetRec/chart']=J.encode({project='P',origin=10000,start=120,finish=210,leadin=4})
reaper={
 ULT_GetMediaItemNote=function()return ''end,
 GetPlayState=function()return playstate end,GetPlayPosition=function()return position end,
 GetCursorPosition=function()return position end,
 GetProjExtState=function(_,sec,key)
  if sec=='ReaSet' and key=='projectId'then return 1,project end
  if sec=='ReaSetSong' and key=='song:7:document'then return 1,document end
  return 0,''
 end,
 GetExtState=function(sec,key)return wire[sec..'/'..key]or''end,
 SetExtState=function(sec,key,v)wire[sec..'/'..key]=v end,
 EnumProjectMarkers2=function(_,i)
  if i==0 then return 1,true,120,210,'Song',7 end
  if i==1 then return 1,true,300,390,'Other song',8 end
  return 0
 end,
 CountTracks=function()return 0 end,
 time_precise=function()return 1 end,EnumProjects=function()return 1 end,
 GetProjectStateChangeCount=function()return csc end,
 get_action_context=function()return 0,'',0,0 end,
 SetToggleCommandState=function()end,
 defer=function(fn)tick=fn end,atexit=function(fn)cleanup=fn end,
 ShowConsoleMsg=function(msg)error(msg)end}
function payload()
 local gen,n=wire['ReaSetCL/meta']:match('^(%d+):(%d+)$');local chunks={}
 for i=0,tonumber(n)-1 do chunks[#chunks+1]=wire['ReaSetCL/d'..i]:match('^%d+:(.*)$')end
 return J.decode(table.concat(chunks))
end
dofile(root..'/Requirements/ReaSet_ChordsLyrics.lua')
''')

    def test_bridge_keeps_original_song_and_document_during_countin_capture_and_pause(self):
        for state,position in [(5,9996),(5,10040),(6,10040),(5,10080)]:
            self.lua.execute(f'playstate={state};position={position};tick()')
            self.assertEqual(self.lua.eval('payload().song.id'),7)
            self.assertEqual(self.lua.eval('payload().capture.origin'),10000)
            self.assertEqual(self.lua.eval('#payload().document.sections'),3)
        self.lua.execute('playstate=0;position=120;csc=csc+1;tick()')
        self.assertTrue(self.lua.eval('payload().capture==J.null'))
        self.assertEqual(self.lua.eval('payload().song.id'),7)

    def test_stale_capture_context_from_another_project_is_ignored(self):
        self.lua.execute("project='Other';csc=csc+1;tick()")
        self.assertTrue(self.lua.eval('payload().song==J.null'))

    def test_controller_state_publishes_journal_capture_coordinates(self):
        source=(ROOT/'Requirements/ReaSet_RecordingCore.lua').read_text(encoding='utf-8')
        state=source[source.index('  function self:state()'):source.index('  -- Restore preview overrides',source.index('  function self:state()'))]
        self.lua.execute('''
s={id='session',song={start=120,finish=210},takes={},parts={}};t={origin=10000,leadin=4,layers={}}
M={tracks=function()return {}end,mix_take=function()return s,t end,
 P={songs=function()return {}end,items=function()return {}end}}
P=M.P
self={id='P',db={inputs={},sessions={s},active={origin=10000}},selected='session',take='take',session=function()return s end}
''')
        self.lua.execute(state)
        self.assertEqual(self.lua.eval('self:state().capture.origin'),10000)
        self.assertEqual(self.lua.eval('self:state().capture.start'),120)
        self.lua.execute('self.db.active=nil')
        self.assertIsNone(self.lua.eval('self:state().capture'))


class RecordingChartDisplayTests(unittest.TestCase):
    setUpClass=classmethod(bt.BrowserTests.setUpClass.__func__)
    tearDownClass=classmethod(bt.BrowserTests.tearDownClass.__func__)
    setUp=bt.BrowserTests.setUp
    tearDown=bt.BrowserTests.tearDown
    load_reaset=bt.BrowserTests.load_reaset
    load=charts.DisplayTests.load
    def test_recording_position_follows_song_in_both_views(self):
        self.load()
        self.page.evaluate('''() => {
          g_clData.song.start=120;g_clData.song.end=210;
          g_clData.capture={origin:10000,start:120,finish:210,leadin:4};
          isPlaying=true;isRecording=true;currentPos=9996;
          renderChordsView();renderLyricsView();
        }''')
        for position, section in [(9996, '0'), (10000, '0'), (10085, '2'), (10005, '0')]:
            self.page.evaluate('p=>{currentPos=p;renderChordsView();renderLyricsView()}', position)
            for host in ('#chords-live', '#lyrics-live'):
                self.assertEqual(self.page.locator(host+' .uc-select').input_value(), section)
                self.assertEqual(self.page.locator(host+' .uc-follow').inner_text(), 'Following')
        self.page.evaluate('isRecording=false;currentPos=125;renderChordsView()')
        self.assertEqual(self.page.locator('#chords-live .uc-select').input_value(), '0')

    def test_recording_pages_and_manual_follow_recovery(self):
        self.load()
        self.page.evaluate('''g_clData.capture={origin:10000,start:0,finish:90};
          isRecording=true;isPlaying=true;currentPos=10005;renderChordsView()''')
        host=self.page.locator('#chords-live')
        host.get_by_role('button',name='Pages',exact=True).click()
        self.assertEqual(host.locator('.uc-select').input_value(),'0')
        host.get_by_role('button',name='Next',exact=True).click()
        self.page.evaluate('currentPos=10085;renderChordsView()')
        self.assertEqual(host.locator('.uc-follow').inner_text(),'Resume following')
        host.locator('.uc-follow').click()
        self.assertEqual(host.locator('.uc-select').input_value(),'2')
        self.page.evaluate('isPlaying=false;renderChordsView()')
        self.assertEqual(host.locator('.uc-select').input_value(),'2')

    def test_recording_mapping_tolerates_published_song_start_rounding(self):
        self.load()
        self.page.evaluate('''g_clData.song.start=120.123;
          g_clData.capture={origin:10000,start:120.1234,finish:210};
          isRecording=true;currentPos=10005;renderChordsView()''')
        self.assertEqual(self.page.locator('#chords-live .uc-select').input_value(),'0')

    def test_chart_layout_recovers_after_no_song_and_tablet_rotation(self):
        self.load()
        self.page.evaluate('window.savedChart=g_clData;g_clData=null;renderChordsView();renderLyricsView()')
        self.assertFalse(self.page.locator('#chords-live').evaluate("n=>n.classList.contains('uc-host')"))
        self.page.evaluate('g_clData=savedChart;renderChordsView();renderLyricsView()')
        for w, h in [(768, 1024), (1024, 768), (1366, 768)]:
            self.page.set_viewport_size({'width':w, 'height':h})
            self.page.evaluate('renderChordsView();renderLyricsView()')
            self.page.wait_for_timeout(80)
            body = self.page.locator('#chords-live .uc-scroll')
            self.assertGreater(body.evaluate('n=>n.clientWidth'), w*.8)
            self.assertLess(body.evaluate('n=>n.scrollWidth-n.clientWidth'), 3)
        # The other view losing its chart must not remove chord layout styles.
        self.page.evaluate('g_clData.document=null;g_clData.lyrics=[];renderLyricsView()')
        self.assertTrue(self.page.locator('#chords-panel').evaluate("n=>n.classList.contains('source-chart')"))

    def test_reading_area_expansion_rewraps_without_resizing_outer_panel(self):
        self.load()
        self.page.evaluate('''() => {
          g_clData.document.revision='width-regression';
          g_clData.document.sections[0].rows=[{id:'long-line',text:'This original sentence needs the full tablet width to be readable while playing',anchors:[]}];
          const body=document.querySelector('#chords-live .uc-scroll');body.style.width='220px';
          renderChordsView();
        }''')
        self.page.wait_for_timeout(100)
        small=self.page.locator('#chords-live [data-section="0"] .uc-line').count()
        outer=self.page.locator('#chords-live').evaluate('n=>n.clientWidth')
        self.page.evaluate("document.querySelector('#chords-live .uc-scroll').style.width=''")
        self.page.wait_for_function('''small=>document.querySelectorAll('#chords-live [data-section="0"] .uc-line').length<small''',arg=small)
        self.assertEqual(self.page.locator('#chords-live').evaluate('n=>n.clientWidth'),outer)


if __name__ == '__main__':
    unittest.main()
