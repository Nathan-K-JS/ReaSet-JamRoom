"""Exercise Python -> actual Lua data, not only a mocked transaction request."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from lupa import LuaRuntime
import jamroom_importer_server as server


class ClickWireTests(unittest.TestCase):
    def test_muted_and_unmuted_survive_the_real_lua_serializer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for muted in (True,False):
                op=root/str(muted)
                reply=json.dumps({'operation':op.name,'status':'ok','message':'updated'})
                with patch.object(server,'TOOLDIR',root),patch.object(server,'_trigger_reaper_action',return_value=reply):
                    server._push_song_items({},'Song',{'id':1,'start':0,'end':60,'project':'P'},operation_dir=op,
                                            click={'file':'test.wav','revision':'r','muted':muted})
                data=LuaRuntime().execute((root/'jamroom_pending_rechord.lua').read_text(encoding='utf-8'))
                self.assertIs(data['click']['muted'],muted)
