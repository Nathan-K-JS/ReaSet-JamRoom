"""Run the production tempo bridge through project and take switches."""
from pathlib import Path
import unittest
from lupa import LuaRuntime


class TempoTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
projects={};active=1;wire={};clock=0;csc=0
for i=1,2 do projects[i]={rate=1,ext={['ReaSet/projectId']='P'..i},
  item={active=1,takes={{guid='a'..i,D_PITCH=0,B_PPITCH=0,I_PITCHMODE=0},
                        {guid='b'..i,D_PITCH=1,B_PPITCH=0,I_PITCHMODE=1}}}} end
local function project()return projects[active]end
reaper={
 EnumProjects=function()return active end,ValidatePtr=function(p)return projects[p]~=nil end,
 SelectProjectInstance=function(p)active=p end,
 GetProjExtState=function(_,sec,key)return 1,project().ext[sec..'/'..key] or '' end,
 SetProjExtState=function(_,sec,key,value)project().ext[sec..'/'..key]=value;return 1 end,
 SetExtState=function(sec,key,v)wire[sec..'/'..key]=v end,
 GetExtState=function(sec,key)return wire[sec..'/'..key] or ''end,
 EnumProjectMarkers2=function(_,i)if i==0 then return 1,true,0,60,'Song',1 end return 0 end,
 CountTracks=function()return 1 end,GetTrack=function()return project()end,
 GetTrackName=function()return true,'[JR:GTR1] Guitar'end,GetMediaTrackInfo_Value=function()return 0 end,
 CountTrackMediaItems=function()return 1 end,GetTrackMediaItem=function(tr)return tr.item end,
 GetMediaItemInfo_Value=function(_,key)return key=='D_POSITION' and 0 or 60 end,
 CountTakes=function(it)return #it.takes end,GetTake=function(it,n)return it.takes[n+1]end,
 GetActiveTake=function(it)return it.takes[it.active]end,TakeIsMIDI=function()return false end,
 GetSetMediaItemInfo_String=function()return true,'item'end,
 GetSetMediaItemTakeInfo_String=function(tk)return true,tk.guid end,
 GetMediaItemTakeInfo_Value=function(tk,key)return tk[key]end,
 SetMediaItemTakeInfo_Value=function(tk,key,v)tk[key]=v end,
 Master_GetPlayRate=function()return project().rate end,CSurf_OnPlayRateChange=function(rate)project().rate=rate end,
 EnumPitchShiftModes=function(i)return i==1,i==1 and 'elastique Pro' or ''end,
 GetToggleCommandState=function()return 1 end,Main_OnCommand=function()end,
 GetPlayState=function()return 0 end,GetCursorPosition=function()return 1 end,
 ShowConsoleMsg=function()end,UpdateArrange=function()end,
 MarkProjectDirty=function()csc=csc+1 end,GetProjectStateChangeCount=function()return csc end,
 time_precise=function()clock=clock+1;return clock end,
 defer=function(fn)tick=fn end,atexit=function(fn)cleanup=fn end
}
''')
        path=Path(__file__).resolve().parent.parent/'Requirements/ReaSet_TempoKey.lua'
        self.lua.execute(path.read_text(encoding='utf-8'))

    def test_shared_setting_survives_consumption_and_restores_project_on_switch(self):
        self.lua.execute("wire['ReaSetTK/want']='1.2|2||0|60|P1';tick();tick()")
        self.assertEqual(self.lua.eval('projects[1].rate'),1.2)
        self.assertEqual(self.lua.eval('projects[1].item.takes[1].D_PITCH'),2)
        self.lua.execute('active=2;tick()')
        self.assertEqual(self.lua.eval('projects[1].rate'),1)
        self.assertEqual(self.lua.eval('projects[1].item.takes[1].D_PITCH'),0)
        self.assertEqual(self.lua.eval('projects[1].item.takes[1].B_PPITCH'),0)
        self.assertEqual(self.lua.eval('projects[2].item.takes[1].D_PITCH'),0)
        self.lua.execute('active=1;tick()')
        self.assertEqual(self.lua.eval('projects[1].item.takes[1].D_PITCH'),2)

    def test_command_for_another_project_is_ignored(self):
        self.lua.execute("wire['ReaSetTK/want']='1.2|2||0|60|P2';tick()")
        self.assertEqual(self.lua.eval('projects[1].rate'),1)

    def test_cleanup_restores_modified_take_after_active_take_changed(self):
        self.lua.execute("wire['ReaSetTK/want']='1.2|2||0|60|P1';tick();projects[1].item.active=2;cleanup()")
        self.assertEqual(self.lua.eval('projects[1].item.takes[1].D_PITCH'),0)
        self.assertEqual(self.lua.eval('projects[1].item.takes[1].I_PITCHMODE'),0)
        self.assertEqual(self.lua.eval('projects[1].item.takes[2].D_PITCH'),1)


if __name__=='__main__':unittest.main()
