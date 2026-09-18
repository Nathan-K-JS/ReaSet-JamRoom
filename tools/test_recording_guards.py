"""Recording must not let library/loop operations touch another project."""
import json
from pathlib import Path
import tempfile
import unittest
from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parent.parent


class RecordingGuards(unittest.TestCase):
    def test_empty_capture_returns_to_setup_but_never_drops_uncertain_media(self):
        source=(ROOT/'Requirements/ReaSet_RecordingCore.lua').read_text(encoding='utf-8')
        functions=source[source.index('  function self:drop_empty_take('):source.index('  function self:review(')]
        for scenario in ('empty','previous_take','unresolved','unknown_file','recovered_audio'):
            with self.subTest(scenario=scenario):
                lua=LuaRuntime(unpack_returned_tuples=True)
                lua.execute('''
M={tracks=function()return {}end,owned_items=function()end}
reaper={EnumerateFiles=function()return nil end}
take={id='take',number=1,items={},inputs={'1'},before={}}
session={id='session',song={free=true,start=100,finish=100},takes={take},folder='unused'}
self={mode='countin',db={active={session='session',take='take'},sessions={session}}}
function self:session()return session end
function self:restore_options()restored=true end
function self:park()parked=true end
function self:arm()armed=true end
function self:save()saved=true end
function self:recover_audio()end
''')
                if scenario=='previous_take':lua.execute("table.insert(session.takes,1,{id='earlier',status='kept',items={{guid='audio'}}})")
                elif scenario=='unresolved':lua.execute('take.unresolved=true')
                elif scenario=='unknown_file':lua.execute("reaper.EnumerateFiles=function()return 'interrupted.aiff' end")
                elif scenario=='recovered_audio':lua.execute("function self:recover_audio()take.items={{guid='recovered'}} end")
                lua.execute(functions);lua.execute('self:finish()')
                if scenario in ('empty','previous_take'):
                    self.assertEqual(lua.eval('self.mode'),'idle')
                    self.assertTrue(lua.eval('armed and saved and parked and restored'))
                    self.assertEqual(lua.eval('#self.db.sessions'),int(scenario=='previous_take'))
                    if scenario=='previous_take':self.assertEqual(lua.eval('session.takes[1].id'),'earlier')
                else:
                    self.assertEqual(lua.eval('self.mode'),'review')
                    self.assertEqual(lua.eval('#self.db.sessions'),1)
                    self.assertEqual(lua.eval('#session.takes'),1)
                    if scenario=='unknown_file':self.assertTrue(lua.eval('take.unresolved'))

    def test_free_jam_settings_and_session_allocation(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute("""reaper={GetProjectLength=function()return 500 end}
          self={db={sessions={{song={finish=600}}}}};M={guid=function()return 'new-jam' end}
        """)
        install=lua.execute((ROOT/'Requirements/ReaSet_FreeJam.lua').read_text(encoding='utf-8'))
        install(lua.globals().self, lua.globals().M)
        lua.execute("self:jam_settings({bpm=137,beats=3,click=false});song=self:jam_song('freejam')")
        self.assertEqual(lua.eval('song.start'),610)
        self.assertEqual(lua.eval('song.bpm'),137)
        self.assertFalse(lua.eval('song.click'))
        self.assertFalse(lua.eval("pcall(function()self:jam_settings({bpm=0,beats=4,click=true})end)")[0])
        self.assertFalse(lua.eval("pcall(function()self:jam_settings({bpm=100,beats=8,click=true})end)")[0])
        lua.execute("self.db.sessions[2]={song=song};same=self:jam_song(song.key)")
        self.assertTrue(lua.eval('same==song'))
        lua.execute("self.db.sessions[2].exported='done'")
        self.assertIsNone(lua.eval('self:jam_song(song.key)'))
        lua.execute("""length=300;self.jamClick={};reaper.ValidatePtr=function()return true end
          reaper.GetMediaItemInfo_Value=function()return length end
          reaper.GetPlayPosition=function()return 890 end
          reaper.SetMediaItemInfo_Value=function(_,_,v)length=v end
          self:jam_extend({song={start=610}})""")
        self.assertEqual(lua.eval('length'),580)

    def test_loop_cleanup_targets_original_project_when_export_is_opened(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''
active=1;wire={};removed={};repeat_project={}
reaper={ColorToNative=function()return 1 end,
 EnumProjects=function()return active end,ValidatePtr=function()return true end,
 SelectProjectInstance=function(p)active=p end,
 GetProjExtState=function(_,s,k)if k=='recordingProject' then return 1,active==2 and '1' or '' end return 1,'P'..active end,
 GetExtState=function(s,k)return wire[s..'/'..k] or ''end,
 SetExtState=function(s,k,v)wire[s..'/'..k]=v end,
 AddProjectMarker2=function()return 10 end,
 DeleteProjectMarker=function(_,id)removed[#removed+1]={active,id}end,
 EnumProjectMarkers=function()return 0 end,
 GetSetRepeat=function(v)repeat_project[active]=v end,
 GetSet_LoopTimeRange=function()end,UpdateArrange=function()end,
 GetPlayState=function()return 1 end,GetPlayPosition=function()return 5 end,
 defer=function(fn)tick=fn end}
''')
        lua.execute((ROOT/'Requirements/ReaSet_NativeLoop.lua').read_text(encoding='utf-8'))
        lua.execute("wire['ReaSet/nativeLoop']='on';wire['ReaSet/loopStart']='0';wire['ReaSet/loopEnd']='30';tick();active=2;tick()")
        self.assertEqual(lua.eval('#removed'),1)
        self.assertEqual(lua.eval('removed[1][1]'),1)
        self.assertEqual(lua.eval('active'),2)
        self.assertIsNone(lua.eval('repeat_project[2]'))

    def test_song_delete_refuses_owned_recording_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'jamroom_pending_delete.txt').write_text('Song\n0\n60\n')
            script=(ROOT/'tools/jamroom_delete_song.lua').read_text(encoding='utf-8')
            script=script.replace('local pointer = script_dir .. "jamroom_pending_delete.txt"',
                                  'local pointer = '+json.dumps((folder/'jamroom_pending_delete.txt').as_posix()))
            lua=LuaRuntime(unpack_returned_tuples=True)
            lua.execute('''
mutations=0;reply=''
reaper={GetPlayState=function()return 0 end,
 GetProjExtState=function()return 1,'P' end,GetExtState=function()return ''end,
 SetExtState=function(_,_,v)reply=v end,ShowConsoleMsg=function()end,
 EnumProjectMarkers2=function(_,i)if i==0 then return 1,true,0,60,'Song',1 end return 0 end,
 CountTracks=function()return 1 end,GetTrack=function()return {}end,
 CountTrackMediaItems=function()return 1 end,GetTrackMediaItem=function()return {}end,
 GetMediaItemInfo_Value=function()return 0 end,
 GetSetMediaItemInfo_String=function()return true,'session/take'end,
 Undo_BeginBlock=function()mutations=mutations+1;error('Must not start mutation')end}
''')
            lua.execute(script)
            self.assertEqual(lua.eval('mutations'),0)
            self.assertIn('recording session',lua.eval('reply'))


if __name__=='__main__':unittest.main()
