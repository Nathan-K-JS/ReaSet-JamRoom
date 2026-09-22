#!/usr/bin/env python3
"""Regression tests for importer task completion and clean reuse."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import jamroom_importer_server as server  # noqa: E402


class ImporterLifecycleTests(unittest.TestCase):
    def test_other_songs_skip_history_does_not_discard_this_songs_audio(self):
        cfg={'slot_map':{'piano':'KEYS'},'slot_labels':{'KEYS':'Keys'}}
        job={'stems':[{'fadr_name':'piano','file':'stems/piano.wav'}]}
        with tempfile.TemporaryDirectory() as td, patch.object(server,'_preview_file',return_value=Path(td)/'piano.wav'), patch.object(Path,'stat',return_value=type('Stat',(),{'st_size':100,'st_mtime_ns':1})()), patch.object(server.ji,'stem_profile',return_value={'verdict':'sparse','peak_db':-7}):
            stem=server.build_review(job,Path(td),cfg)['stems'][0]
            self.assertEqual(stem['slot'],'EXTRA')
            self.assertNotIn('history_note',stem)
            job['slot_overrides']={'stems/piano.wav':'SKIP'}
            self.assertEqual(server.build_review(job,Path(td),cfg)['stems'][0]['slot'],'SKIP')




    def test_partial_download_still_counts_as_cached_recording(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "source.wav").write_bytes(b"recording")
            self.assertFalse(server.job_has_audio(folder))
            self.assertTrue(server.job_has_cached_audio(folder))




if __name__ == "__main__":
    unittest.main()
