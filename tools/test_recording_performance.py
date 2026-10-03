"""Mute restoration correctness and scaling, using only in-memory REAPER fakes."""
from pathlib import Path
import unittest

from lupa import LuaRuntime


ROOT = Path(__file__).resolve().parent.parent


class RecordingRestoreTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
items={};owned={};tracks={};wire={};lookups=0;guid_reads=0;writes=0
self={audition={},clear_timeline=function()end,jam_clear_click=function()end}
M={tracks=function()return tracks end,
   owned_items=function(fn)for _,it in ipairs(owned)do fn(it)end end}
reaper={
 CountMediaItems=function()return #items end,
 GetMediaItem=function(_,i)lookups=lookups+1;return items[i+1]end,
 GetSetMediaItemInfo_String=function(it,key)
   assert(key=='GUID');guid_reads=guid_reads+1;return true,it.guid
 end,
 SetMediaItemInfo_Value=function(it,key,value)
   assert(not it.deleted,'Stale item pointer');it[key]=value;writes=writes+1
 end,
 SetMediaTrackInfo_Value=function(tr,key,value)tr[key]=value end,
 CountTakes=function(it)return #(it.takes or {})end,
 GetTake=function(it,i)return it.takes[i+1]end,
 GetSetMediaItemTakeInfo_String=function(tk)return true,tk.guid end,
 SetMediaItemTakeInfo_Value=function(tk,key,value)tk[key]=value end,
 CSurf_OnPlayRateChange=function(value)rate=value end,
 SetProjExtState=function(_,section,key,value)wire[key]=value end,
 UpdateArrange=function()redrawn=true end
}
function populate(n)
 for i=1,n do
  local guid='dummy-'..i
  items[i]={guid=guid,B_MUTE=1};self.audition[guid]=i%2
 end
end
''')
        source = (ROOT / 'Requirements/ReaSet_RecordingCore.lua').read_text(encoding='utf-8')
        park = source[source.index('  function self:park()'):source.index('  function self:setup()')]
        self.lua.execute(park)

    def test_library_restore_is_linear_and_preserves_every_original_mute(self):
        self.lua.execute('populate(8388);self:park()')
        self.assertLessEqual(self.lua.eval('lookups'), 8388)
        self.assertLessEqual(self.lua.eval('guid_reads'), 8388)
        self.lua.execute('''
for i,it in ipairs(items)do assert(it.B_MUTE==i%2)end
assert(next(self.audition)==nil)
assert(wire.audition=='' and wire.auditionOptions=='' and redrawn)
''')

    def test_sparse_journal_ignores_missing_guids_and_leaves_other_items_alone(self):
        self.lua.execute('''
items={{guid='zero',B_MUTE=1},{guid='one',B_MUTE=0},{guid='untouched',B_MUTE=2}}
self.audition={zero=0,one=1,deleted=0}
self:park()
assert(items[1].B_MUTE==0 and items[2].B_MUTE==1 and items[3].B_MUTE==2)
assert(writes==2)
-- A second call has no stale journal to reapply over a subsequent manual edit.
items[1].B_MUTE=1;self:park();assert(items[1].B_MUTE==1 and writes==2)
''')

    def test_cleanup_precedes_lookup_and_retains_recording_disarm_and_pitch_restore(self):
        self.lua.execute('''
preview={guid='preview',B_MUTE=1};recorded={guid='recorded',B_MUTE=0}
items={preview,{guid='backing',B_MUTE=1,takes={{guid='pitch',D_PITCH=5}}},recorded}
owned={recorded};tracks={{I_RECARM=1,I_RECMON=1}}
self.audition={preview=0,backing=0}
self.auditionOptions={rate=1,pitches={pitch=0,deleted=3}}
function self:clear_timeline()table.remove(items,1);preview.deleted=true end
function self:jam_clear_click()click_cleared=true end
self:park()
assert(items[1].B_MUTE==0 and items[1].takes[1].D_PITCH==0 and rate==1)
assert(recorded.B_MUTE==1 and tracks[1].I_RECARM==0 and tracks[1].I_RECMON==0)
assert(preview.B_MUTE==1 and click_cleared and self.auditionOptions==nil)
''')

    def test_empty_journal_does_not_add_an_item_scan(self):
        self.lua.execute("items={{guid='unrelated',B_MUTE=0}};self:park()")
        self.assertEqual(self.lua.eval('lookups'), 0)
        self.assertEqual(self.lua.eval('writes'), 0)

    def test_failed_restore_keeps_journal_for_recovery(self):
        self.lua.execute('''
populate(3);wire.audition='durable journal'
reaper.SetMediaItemInfo_Value=function()error('Simulated native failure')end
ok=pcall(function()self:park()end)
assert(not ok and next(self.audition)~=nil and wire.audition=='durable journal')
assert(not redrawn)
''')


if __name__ == '__main__':
    unittest.main()
