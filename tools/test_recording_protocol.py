"""Exercise the actual Lua controller's command/probe ordering without hardware."""
from pathlib import Path
import unittest
from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parent.parent


class RecordingProtocolTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().root = ROOT.as_posix()
        self.lua.execute('''
local original=dofile
wire={};clock=1;mutations=0
local J=original(root..'/Requirements/ReaSet_JSON.lua')
controller={projectfile='test.RPP',id='P',mode='idle',seen={},revision=0,db={}}
function controller:auto_setup()end
function controller:tick()end
function controller:command(c)mutations=mutations+1;self.mode='recording'end
function controller:state()return {project=self.id,mode=self.mode,revision=self.revision,ack=self.ack}end
local M={J=J,guid=function()return 'instance' end,P={reconcile=function()end},new=function()return controller end}
dofile=function(path)
 if path:match('ReaSet_RecordingCore.lua$')then return M end
 if path:match('ReaSet_RecordingExport.lua$')then return function()end end
 return original(path)
end
reaper={SetExtState=function(s,k,v)wire[k]=v end,GetExtState=function(s,k)return wire[k]or''end,
 EnumProjects=function()return 1,'test.RPP'end,GetProjExtState=function()return 0,''end,
 GetProjectStateChangeCount=function()return 0 end,time_precise=function()return clock end,
 atexit=function()end,defer=function(fn)next_tick=fn end,GetPlayState=function()return 0 end}
function send(key,value)wire[key]=J.encode(value)end
function tick()clock=clock+1;next_tick()end
function state()
 local g,n,slot=wire.meta:match('(%d+):(%d+):(%d+)');local parts={}
 for i=0,tonumber(n)-1 do parts[#parts+1]=wire['d'..slot..'_'..i]:match('^%d+:(.*)')end
 return J.decode(table.concat(parts))
end
''')
        self.lua.execute((ROOT/'Requirements/ReaSet_Recording.lua').read_text(encoding='utf-8'))

    def test_probe_cancels_delayed_command_without_recording(self):
        self.lua.execute("send('probe',{project='P',nonce='check',pending='record'});send('want',{project='P',nonce='record',op='record'});tick()")
        self.assertEqual(self.lua.eval('mutations'),0)
        self.assertFalse(self.lua.eval('state().recovery.confirmed'))
        self.lua.execute("send('want',{project='P',nonce='record',op='record'});tick()")
        self.assertEqual(self.lua.eval('mutations'),0)

    def test_probe_finds_completed_command_after_other_browser_ack(self):
        self.lua.execute("send('want',{project='P',nonce='first',op='record'});tick();send('want',{project='P',nonce='second',op='record'});tick();send('probe',{project='P',nonce='check',pending='first'});tick()")
        self.assertEqual(self.lua.eval('mutations'),2)
        self.assertTrue(self.lua.eval('state().recovery.confirmed'))
        self.assertEqual(self.lua.eval('state().instance'),'instance')

    def test_probe_for_another_project_cannot_cancel_current_command(self):
        self.lua.execute("send('probe',{project='other',nonce='check',pending='record'});send('want',{project='P',nonce='record',op='record'});tick()")
        self.assertEqual(self.lua.eval('mutations'),1)


if __name__=='__main__':unittest.main()
