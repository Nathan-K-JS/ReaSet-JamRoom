"""Device opening, independent arrangement state and capture-offset regressions."""
from pathlib import Path
import unittest
from lupa import LuaRuntime

ROOT=Path(__file__).resolve().parent.parent


class RecordingPartsTests(unittest.TestCase):
    def runtime(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.globals().root=ROOT.as_posix()
        lua.execute("M={J=dofile(root..'/Requirements/ReaSet_JSON.lua')}")
        return lua

    def test_prepared_redo_keeps_original_on_failure_and_passes_backing_choice(self):
        lua=self.runtime()
        lua.execute('''reaper={GetPlayState=function()return 0 end}
session={id='s',song={key='song',start=10},takes={{id='old',status='kept'}}}
self={preparation={session='s',take='old',kind='redo'},backingOn=false,stemMutes={BASS=true}}
function self:session()return session end
function self:song()return session.song end
function self:save()end
function self:begin(key,parent,sid,mix)
  received=mix
  assert(not fail,'Input unavailable')
  new={id='new'};session.takes[2]=new
end
M.mix_take=function()return session,new end
dofile(root..'/Requirements/ReaSet_RecordingPrepare.lua')(self,M)
fail=true;ok=pcall(function()self:record_prepared({})end)
''')
        self.assertFalse(lua.eval('ok'))
        self.assertEqual(lua.eval('session.takes[1].status'),'kept')
        self.assertEqual(lua.eval('#session.takes'),1)
        self.assertTrue(lua.eval('self.preparation~=nil'))
        lua.execute('fail=false;self:record_prepared({stopAtEnd=false})')
        self.assertFalse(lua.eval('received.backingOn'))
        self.assertTrue(lua.eval('received.stemMutes.BASS'))
        self.assertEqual(lua.eval('session.takes[1].status'),'discarded')
        self.assertFalse(lua.eval('new.stopAtEnd'))
        self.assertTrue(lua.eval('self.preparation==nil'))

    def test_device_opens_before_channels_are_available_and_restores_preferences(self):
        lua=self.runtime()
        lua.execute('''clock=0;channels=0;settings={audiocloseinactive=11,audioclosestop=1}
reaper={GetPlayState=function()return playing or 0 end,time_precise=function()return clock end,
SNM_GetIntConfigVar=function(k)return settings[k]end,SNM_SetIntConfigVar=function(k,v)settings[k]=v end,
GetNumAudioInputs=function()return channels end,Audio_Init=function()opened=true end}
self={db={},root='saved'};function self:save()saved=true end
dofile(root..'/Requirements/ReaSet_RecordingReady.lua')(self,M)
self:prepare_device();self:device_tick()
''')
        self.assertTrue(lua.eval('opened and saved'))
        self.assertEqual(lua.eval('self.deviceState'),'connecting')
        self.assertEqual(lua.eval('settings.audiocloseinactive'),8)
        lua.execute('channels=16;self:device_tick()')
        self.assertEqual(lua.eval('self.deviceState'),'ready')
        lua.execute('self:release_device()')
        self.assertEqual(lua.eval('settings.audiocloseinactive'),11)
        self.assertEqual(lua.eval('settings.audioclosestop'),1)
        lua.execute('playing=5')
        self.assertFalse(lua.eval('pcall(function()self:prepare_device()end)')[0])

    def test_device_failure_is_bounded_and_retry_can_recover_without_playing(self):
        lua=self.runtime()
        lua.execute('''clock=0;channels=0
reaper={GetPlayState=function()return 0 end,time_precise=function()return clock end,
SNM_GetIntConfigVar=function()return 0 end,SNM_SetIntConfigVar=function()end,
GetNumAudioInputs=function()return channels end,Audio_Init=function()end}
self={db={},root='saved'};function self:save()end
dofile(root..'/Requirements/ReaSet_RecordingReady.lua')(self,M)
self:prepare_device();clock=6;self:device_tick()
''')
        self.assertEqual(lua.eval('self.deviceState'),'unavailable')
        lua.execute('self:prepare_device();channels=16;self:device_tick()')
        self.assertEqual(lua.eval('self.deviceState'),'ready')

    def test_preroll_alignment_preserves_raw_audio_offset_and_is_idempotent(self):
        lua=self.runtime()
        lua.execute('''it={D_POSITION=100,D_LENGTH=7};tk={D_STARTOFFS=0,D_PLAYRATE=1.25};tag=''
M.ext=function(_,_,v)if v then tag=v end return tag end
reaper={GetMediaItemInfo_Value=function(_,k)return it[k]end,
SetMediaItemInfo_Value=function(_,k,v)it[k]=v end,CountTakes=function()return 1 end,
GetTake=function()return tk end,GetMediaItemTakeInfo_Value=function(_,k)return tk[k]end,
SetMediaItemTakeInfo_Value=function(_,k,v)tk[k]=v end}
self={};dofile(root..'/Requirements/ReaSet_RecordingTimeline.lua')(self,M)
session={song={start=10}};take={origin=104}
assert(self:align_capture(session,take,it));assert(self:align_capture(session,take,it))
''')
        self.assertEqual(lua.eval('it.D_POSITION'),10)
        self.assertEqual(lua.eval('it.D_LENGTH'),3)
        self.assertEqual(lua.eval('tk.D_STARTOFFS'),5)

    def test_selected_arrangement_keeps_dependencies_even_if_source_take_discarded(self):
        lua=self.runtime()
        lua.execute('''dofile(root..'/Requirements/ReaSet_RecordingParts.lua')(M)
s={takes={{status='discarded',items={{track='part1',guid='one'}}},{items={{track='part2',guid='two'}}},{items={{track='alternative',guid='three'}}}}}
t={layers={'part1','part2'},mix={part1={gain=.25},part2={gain=1}}}
rows=M.arrangement({},s,t)
''')
        self.assertEqual(lua.eval('#rows'),2)
        self.assertEqual(lua.eval('rows[1].guid'),'one')
        lua.execute('s.takes[1].unresolved=true')
        self.assertFalse(lua.eval('pcall(function()M.arrangement({},s,t)end)')[0])
