"""Import handoff guards: fake HTTP and Lua APIs, disposable folders only."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from lupa import LuaRuntime
import jamroom_import as ji


class ApplyRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root/'job'; self.folder.mkdir()
        self.tools = self.root/'tools'; self.tools.mkdir()
        self.cfg = {'reaper_web':'http://reaper.test', 'auto_apply':True}
        self.job = {'import_operation':'original-operation'}

    def test_transport_must_be_confirmed_stopped(self):
        for state in (1, 2, 5, 6, 'bad'):
            with self.subTest(state=state), patch.object(ji.requests, 'get', return_value=Mock(text=f'TRANSPORT\t{state}\t10')):
                with self.assertRaises(RuntimeError):ji.require_stopped_for_import(self.cfg)
        with patch.object(ji.requests, 'get', return_value=Mock(text='TRANSPORT\t0\t10')):
            ji.require_stopped_for_import(self.cfg)
        with patch.object(ji.requests, 'get', side_effect=ji.requests.ConnectionError):
            with self.assertRaisesRegex(RuntimeError, 'Could not check'):ji.require_stopped_for_import(self.cfg)

    def test_late_pause_preserves_receipts_and_does_not_submit_or_write_pointer(self):
        applied = self.folder/'applied.txt'; applied.write_text('Previous receipt')
        with patch.object(ji, '__file__', str(self.tools/'jamroom_import.py')), \
             patch.object(ji.requests, 'get', return_value=Mock(text='TRANSPORT\t2\t10')) as get:
            with self.assertRaisesRegex(RuntimeError, 'paused'):
                ji.stage_apply(self.job, self.folder, self.cfg, True)
        self.assertEqual(get.call_count, 1)
        self.assertFalse((self.tools/'jamroom_pending_job.txt').exists())
        self.assertEqual(applied.read_text(), 'Previous receipt')

    def handoff(self, trigger, sleep=None):
        def get(url, **kwargs):
            if url.endswith('/TRANSPORT'):return Mock(status_code=200, text='TRANSPORT\t0\t10')
            if url.endswith('/import_cmd'):return Mock(status_code=200, text='EXTSTATE\tReaSetJR\timport_cmd\t_TEST_APPLY')
            self.assertTrue(url.endswith('/_TEST_APPLY'))
            trigger()
            return Mock(status_code=200, text='')
        with patch.object(ji, '__file__', str(self.tools/'jamroom_import.py')), \
             patch.object(ji.requests, 'get', side_effect=get), \
             patch.object(ji.time, 'sleep', side_effect=sleep or AssertionError('Unexpected receipt wait')), \
             patch.object(ji.subprocess, 'Popen', side_effect=AssertionError('Must not launch REAPER')):
            ji.stage_apply(self.job, self.folder, self.cfg, True)

    def test_native_rejection_returns_immediately_and_old_error_is_cleared(self):
        rejected = self.folder/'apply-error.txt'; rejected.write_text('original-operation\nStale error')
        def trigger():
            self.assertFalse(rejected.exists())
            rejected.write_text('original-operation\nFinish the recording session and choose Done')
        with self.assertRaisesRegex(RuntimeError, 'Finish the recording session'):
            self.handoff(trigger)

    def test_another_operations_error_is_ignored_until_confirmation(self):
        def trigger(): (self.folder/'apply-error.txt').write_text('different-operation\nWrong error')
        def confirm(_): (self.folder/'applied.txt').write_text('Already applied: dummy song')
        self.handoff(trigger, confirm)
        self.assertTrue((self.folder/'applied.txt').exists())

    def run_lua(self, state=0, locked=False, receipt=''):
        source = Path(__file__).with_name('jamroom_import_apply.lua')
        script = self.tools/source.name; script.write_bytes(source.read_bytes())
        (self.tools/'jamroom_pending_job.txt').write_text(self.folder.as_posix())
        (self.folder/'job_for_reaper.lua').write_text("return {region_name='Dummy song',import_operation='original-operation',target_project='dummy-project',slots={}}")
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.globals().playstate = state; lua.globals().locked = locked; lua.globals().receipt = receipt
        lua.execute('''
reaper={
 ULT_SetMediaItemNote=function()error('Unexpected item mutation')end,
 CountTracks=function()return 1 end, GetTrack=function()return {}end,
 GetTrackName=function()return true,'PB BASS'end,
 GetMediaTrackInfo_Value=function()return 0 end,
 EnumProjectMarkers2=function(_,i)
   if receipt=='12' and i==0 then return 1,true,0,60,'Dummy song',12 end
   return 0 end,
 CountMediaItems=function()return 0 end, CountTrackMediaItems=function()return 0 end,
 GetProjExtState=function(_,sec,key)
   if sec=='ReaSet' then return 1,'dummy-project' end
   if sec=='ReaSetImport' then return 1,receipt end
   if sec=='ReaSetSong' then return 1,'original-operation' end
   error('Unexpected read')end,
 GetPlayState=function()return playstate end,
 GetExtState=function()return locked and 'dummy-project' or '' end,
 SetExtState=function(_,_,value)status=value end,
 ShowConsoleMsg=function()end
}
setmetatable(reaper,{__index=function(_,key)error('Unexpected REAPER call: '..key)end})
''')
        lua.execute('dofile(...)', script.as_posix())
        return lua

    def test_native_pause_and_recording_lock_reject_before_any_project_mutation(self):
        for state, locked, message in ((2,False,'Pause is not Stop'), (0,True,'choose Done')):
            with self.subTest(state=state):
                self.run_lua(state, locked)
                error = (self.folder/'apply-error.txt').read_text()
                self.assertTrue(error.startswith('original-operation\n'))
                self.assertIn(message, error)
                self.assertFalse((self.folder/'applied.txt').exists())

    def test_native_retry_reconciles_existing_receipt_without_appending(self):
        self.run_lua(receipt='12')
        self.assertIn('Already applied', (self.folder/'applied.txt').read_text())
        self.assertFalse((self.tools/'jamroom_pending_job.txt').exists())

    def test_native_partial_append_receipt_never_retries_as_new_import(self):
        self.run_lua(receipt='pending')
        self.assertIn('unresolved', (self.folder/'apply-error.txt').read_text())
        self.assertFalse((self.folder/'applied.txt').exists())


if __name__ == '__main__':unittest.main()
