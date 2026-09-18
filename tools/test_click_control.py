"""Exercise the running Jam Room bridge against muted click items."""
import json
from pathlib import Path
import unittest
from lupa import LuaRuntime


class ClickControlTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
wire={};csc=0;project=1
tracks={
 {name='PB CLICK',I_FOLDERDEPTH=1,B_MUTE=0,items={}},
 {name='[JR:CLICK] Click',I_FOLDERDEPTH=-1,B_MUTE=1,items={
   {D_POSITION=0,D_LENGTH=60,B_MUTE=1},
   {D_POSITION=80,D_LENGTH=60,B_MUTE=1}}}}
reaper={
 time_precise=function()return 1 end,
 CountTracks=function()return #tracks end,GetTrack=function(_,i)return tracks[i+1]end,
 GetTrackName=function(tr)return true,tr.name end,
 GetMediaTrackInfo_Value=function(tr,k)return tr[k] or 0 end,
 SetMediaTrackInfo_Value=function(tr,k,v)tr[k]=v;csc=csc+1 end,
 CountTrackMediaItems=function(tr)return #tr.items end,
 GetTrackMediaItem=function(tr,i)return tr.items[i+1]end,
 GetMediaItemInfo_Value=function(it,k)return it[k] or 0 end,
 SetMediaItemInfo_Value=function(it,k,v)it[k]=v;csc=csc+1 end,
 EnumProjectMarkers2=function(_,i)
   if i==0 then return 1,true,0,60,'One',1 end
   if i==1 then return 1,true,80,140,'Two',2 end
   return 0
 end,
 SetExtState=function(s,k,v)wire[s..'/'..k]=v end,
 GetExtState=function(s,k)return wire[s..'/'..k] or ''end,
 GetProjectStateChangeCount=function()return csc end,
 EnumProjects=function()return project end,
 Undo_BeginBlock=function()end,Undo_EndBlock=function()end,UpdateArrange=function()end,
 defer=function(fn)tick=fn end,atexit=function(fn)cleanup=fn end
}
''')
        self.lua.execute((Path(__file__).resolve().parent.parent / 'Requirements/ReaSet_JamRoom.lua').read_text(encoding='utf-8'))
        self.lua.execute('tick()')

    def payload(self):
        wire = self.lua.globals().wire
        count = int(wire['ReaSetJR/meta'].split(':')[1])
        return json.loads(''.join(wire[f'ReaSetJR/d{i}'].split(':', 1)[1] for i in range(count)))

    def request(self, key, mute):
        self.lua.globals().wire['ReaSetJR/clickWant'] = key + '|' + str(mute)
        self.lua.execute('tick();tick()')

    def test_enable_clears_current_item_and_track_but_preserves_other_song(self):
        control = self.payload()['songs']['1']['controls'][0]
        self.assertTrue(control['clickBlocked'])
        self.request(control['clickKey'], 0)
        self.assertEqual(self.lua.eval('tracks[2].B_MUTE'), 0)
        self.assertEqual(self.lua.eval('tracks[2].items[1].B_MUTE'), 0)
        self.assertEqual(self.lua.eval('tracks[2].items[2].B_MUTE'), 1)
        control = self.payload()['songs']['1']['controls'][0]
        self.assertFalse(control['clickBlocked'])
        self.request(control['clickKey'], 1)
        self.assertEqual(self.lua.eval('tracks[1].B_MUTE'), 1)

    def test_old_project_or_changed_items_reject_command(self):
        for change in ('project=2', 'csc=csc+1'):
            key = self.payload()['songs']['1']['controls'][0]['clickKey']
            self.lua.execute(change)
            self.request(key, 0)
            self.assertEqual(self.lua.eval('tracks[2].items[1].B_MUTE'), 1)

