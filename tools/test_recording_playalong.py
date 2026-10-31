"""Complete musician workflow in an intercepted browser; no live endpoints."""
import json
import unittest

from lupa import LuaRuntime
import test_browser as bt
from test_recording_chart import NativeChartBridgeTests, ROOT
from test_unified_chart import document


class BridgeTransitions(NativeChartBridgeTests):
    def test_loaded_chart_enters_leaves_and_reenters_capture_without_project_edits(self):
        self.lua.execute('playstate=0;position=120;tick()')
        self.assertTrue(self.lua.eval('payload().capture==J.null'))
        # Chart cached for the same song; EXTSTATE/transport changes do not edit the project.
        for origin in (10000, 11000):
            self.lua.execute(f"wire['ReaSetRec/chart']=J.encode({{project='P',origin={origin},start=120,finish=210,leadin=4}});playstate=5;position={origin}-4;tick()")
            self.assertEqual(self.lua.eval('payload().capture.origin'),origin)
            self.lua.execute('playstate=0;position=120;tick()')
            self.assertTrue(self.lua.eval('payload().capture==J.null'))
        self.assertEqual(self.lua.eval('csc'),1)

    def test_capture_arriving_after_transport_republishes_same_song(self):
        self.lua.execute("wire['ReaSetRec/chart']='';playstate=5;position=120;tick()")
        self.assertTrue(self.lua.eval('payload().capture==J.null'))
        self.lua.execute("wire['ReaSetRec/chart']=J.encode({project='P',origin=120,start=120,finish=210});tick()")
        self.assertEqual(self.lua.eval('payload().capture.origin'),120)


class SongSelection(unittest.TestCase):
    def test_song_selection_is_stopped_scoped_and_preserves_inputs(self):
        source=(ROOT/'Requirements/ReaSet_RecordingCore.lua').read_text(encoding='utf-8')
        command=source[source.index('  function self:command(c)'):source.index('  function self:tick()')]
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute("""transport=0;cursor=0
reaper={GetPlayState=function()return transport end,SetEditCurPos=function(pos,move,seek)assert(not move and not seek);cursor=pos end}
self={id='P',revision=1,mode='idle',db={inputs={{selected=true}}}}
function self:song(key)assert(key=='second');return {start=120,finish=210}end
""")
        lua.execute(command)
        lua.execute("self:command({op='song',project='P',revision=1,song='second'})")
        self.assertEqual(lua.eval('cursor'),120)
        self.assertTrue(lua.eval('self.db.inputs[1].selected'))
        for mode, transport in [('recording',5),('review',0),('idle',1),('idle',2)]:
            lua.globals().self.mode=mode;lua.globals().transport=transport
            self.assertFalse(lua.eval("pcall(function()self:command({op='song',project='P',revision=1,song='second'})end)")[0])


class PlayalongTests(unittest.TestCase):
    setUpClass=classmethod(bt.BrowserTests.setUpClass.__func__)
    tearDownClass=classmethod(bt.BrowserTests.tearDownClass.__func__)
    setUp=bt.BrowserTests.setUp
    tearDown=bt.BrowserTests.tearDown
    load_reaset=bt.BrowserTests.load_reaset
    recording_state=bt.BrowserTests.recording_state

    def load(self):
        self.recording_state()
        self.page.evaluate('''doc=>{
          g_clData={schema:1,project:'test',song:{id:7,name:'Play-along song',start:120,end:210},document:doc};
          g_recState.device='ready';g_recState.songKey='second';
          g_recState.songs.push({key:'second',name:'Play-along song',start:120,finish:210,gain:.65});
          currentPos=120;renderChordsView();recRender();
        }''',document())

    def publish(self, **updates):
        self.page.evaluate('''updates=>{
          const s=Object.assign({},g_recState,updates);
          s.revision++;s.ack=g_recPending?.nonce;
          g_recHb={val:String(s.revision),at:Date.now()};
          recHandleExtState(['EXTSTATE','ReaSetRec','meta',s.revision+':1:0']);
          recHandleExtState(['EXTSTATE','ReaSetRec','d0_0',s.revision+':'+JSON.stringify(s)]);
        }''',updates)

    def transport(self, state, pos):
        self.page.evaluate("v=>wwr_onreply('TRANSPORT\\t'+v[0]+'\\t'+v[1]+'\\t0\\t0\\n')",[state,pos])

    def capture(self, take='t1', origin=10000, mode='countin'):
        session=dict(id='s',song=dict(key='second',name='Play-along song',start=120,finish=210),
                     takes=[dict(id=take,number=1,inputs=['1'],duration=0,status='recording')])
        self.publish(mode=mode,selected='s',take=take,sessions=[session],preparation=None,
                     capture=dict(project='test',origin=origin,start=120,finish=210,leadin=4),elapsed=0)
        self.transport(5,origin-4 if mode=='countin' else origin)

    def stop(self):
        sessions=self.page.evaluate('g_recState.sessions')
        sessions[0]['takes'][0].update(duration=85,status='kept')
        self.transport(0,120)
        self.publish(mode='review',sessions=sessions,capture=None,paused=False,parts=[])

    def section(self, expected):
        self.assertEqual(self.page.locator('#chords-live .uc-select').input_value(),str(expected))
        self.assertEqual(self.page.locator('#chords-live .uc-follow').inner_text(),'Following')

    def test_choose_song_inputs_record_chart_pause_stop_review_and_another_take(self):
        self.load()
        self.page.locator('#rec-song').select_option('song1')
        self.assertEqual(self.page.evaluate('g_recPending.op'),'song')
        self.assertEqual(self.page.locator('#rec-song').input_value(),'second')
        self.publish(songKey='song1')
        self.page.locator('#rec-song').select_option('second')
        self.publish(songKey='second')
        self.page.get_by_label('Record Vox 2',exact=True).click()
        inputs=self.page.evaluate('g_recState.inputs');inputs[1]['selected']=True
        self.publish(inputs=inputs)
        self.page.get_by_role('button',name='Record',exact=True).click()
        self.assertTrue(self.page.locator('#recording-panel').is_visible())
        self.assertFalse(self.page.locator('#rec-playing').is_visible())
        self.capture()
        self.assertFalse(self.page.locator('#recording-panel').is_visible())
        self.assertTrue(self.page.locator('#chords-panel').is_visible())
        self.assertIn('Vox 2',self.page.locator('#rec-playing').inner_text())
        self.section(0)
        self.publish(mode='recording',elapsed=40)
        self.transport(5,10040);self.section(1)
        self.page.locator('#main-play-btn').click()
        self.assertEqual(self.page.evaluate('g_recPending.op'),'pause')
        self.publish(paused=True);self.transport(6,10040);self.section(1)
        self.assertIn('RESUME',self.page.locator('#main-play-btn').inner_text())
        self.page.locator('#main-play-btn').click();self.publish(paused=False)
        self.transport(5,10085);self.section(2)
        self.assertEqual(self.page.get_by_role('button',name='Discard take',exact=True).count(),0)
        self.page.locator('#main-stop-btn').click()
        self.assertEqual(self.page.evaluate('g_recPending.op'),'stop')
        self.assertFalse(self.page.locator('#recording-panel').is_visible())
        self.stop()
        self.assertTrue(self.page.get_by_role('button',name='Discard take',exact=True).is_visible())
        self.assertTrue(self.page.get_by_role('button',name='Add part',exact=True).is_visible())
        self.page.get_by_role('button',name='New take',exact=True).click()
        self.publish(preparation=dict(kind='new',session='s',take='t1'))
        self.page.get_by_role('button',name='Record take',exact=True).click()
        # The chart still carries the first take's coordinates; the controller is newer.
        self.page.evaluate('g_clData.capture={project:"test",origin:10000,start:120,finish:210}')
        self.capture('t2',11000)
        self.section(0)
        self.publish(mode='recording');self.transport(5,11085);self.section(2)
        self.stop()
        self.assertTrue(self.page.get_by_role('button',name='Export recording',exact=True).is_visible())

    def test_capture_keeps_tablet_chart_full_width_and_transport_accessible(self):
        self.load();self.capture()
        for width,height in [(768,1024),(1024,768),(1366,768),(390,844),(844,390)]:
            self.page.set_viewport_size(dict(width=width,height=height))
            self.page.wait_for_timeout(100)
            body=self.page.locator('#chords-live .uc-scroll')
            self.assertGreater(body.evaluate('n=>n.clientWidth'),width*.8)
            self.assertLessEqual(body.bounding_box()['y']+body.bounding_box()['height'],self.page.locator('#perfBar').bounding_box()['y']+1)
            stop=self.page.locator('#main-stop-btn').bounding_box()
            self.assertLessEqual(stop['y']+stop['height'],height)
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.locator('#tab-btn-recording').click()
        self.assertTrue(self.page.locator('#chords-panel').is_visible())

    def test_other_tablet_resumes_following_but_does_not_open_take_management(self):
        self.load()
        self.page.evaluate("document.getElementById('recording-panel').classList.remove('open');toggleChordsPanel();ChartDisplay.setMode(document.getElementById('chords-live'),'lyrics');renderChordsView()")
        self.page.locator('#chords-live .uc-select').select_option('2')
        self.capture();self.section(0)
        self.assertFalse(self.page.locator('#chords-live').get_by_label('Show chords',exact=True).is_checked())
        self.publish(mode='recording');self.transport(5,10085);self.section(2)
        self.stop()
        self.assertFalse(self.page.locator('#recording-panel').is_visible())
        self.assertTrue(self.page.locator('#chords-panel').is_visible())

    def test_manual_browse_survives_updates_and_disconnection_keeps_stop(self):
        self.load();self.capture()
        self.page.locator('#chords-live .uc-select').select_option('2')
        self.publish(mode='recording');self.transport(5,10010)
        self.assertEqual(self.page.locator('#chords-live .uc-select').input_value(),'2')
        self.page.locator('#chords-live .uc-follow').click();self.section(0)
        self.page.evaluate('g_recHb.at=0;recRender()')
        self.assertIn('Connection lost',self.page.locator('#rec-playing').inner_text())
        self.page.locator('#main-stop-btn').click()
        self.assertEqual(self.page.evaluate('sent.at(-1)'),1016)

    def test_failed_record_stays_at_setup_and_stale_project_cannot_open_capture(self):
        self.load();self.page.get_by_role('button',name='Record',exact=True).click()
        self.publish(error='Input unavailable')
        self.assertTrue(self.page.locator('#recording-panel').is_visible())
        self.assertIn('Input unavailable',self.page.locator('#recording-body').inner_text())
        self.publish(project='other',mode='recording',capture=dict(project='other',origin=10000,start=120,finish=210))
        self.assertFalse(self.page.locator('#rec-playing').is_visible())

    def test_native_record_bit_blocks_song_automation_before_controller_snapshot(self):
        self.load()
        self.page.evaluate('''g_recState=null;g_recPending=null;
          displayList=[{id:'7',name:'Play-along song',start:120,end:210,duration:90,skipped:true},
            {id:'8',name:'Next song',start:220,end:300,duration:80}];sent=[];''')
        self.transport(5,125)
        self.assertTrue(self.page.evaluate('recLocked()'))
        self.assertFalse(self.page.evaluate("sent.some(x=>String(x).includes('SET/POS')||x===1016||x===1007)"))

    def test_tablet_joining_during_capture_opens_chart_without_claiming_review(self):
        self.load()
        self.page.evaluate("document.getElementById('recording-panel').classList.remove('open');updateTopTabs()")
        self.capture(mode='recording')
        self.assertTrue(self.page.locator('#chords-panel').is_visible())
        self.stop()
        self.assertFalse(self.page.locator('#recording-panel').is_visible())


if __name__=='__main__':unittest.main()
