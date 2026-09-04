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
    def setUp(self):
        self.old_state = dict(server.STATE)
        self.old_current = dict(server.CURRENT)

    def tearDown(self):
        if server.BUSY.locked():
            server.BUSY.release()
        server.STATE.clear()
        server.STATE.update(self.old_state)
        server.CURRENT.clear()
        server.CURRENT.update(self.old_current)

    def test_rebuild_discards_old_analysis_but_keeps_routing(self):
        old = {
            "schema": 1,
            "stages": {"download": True, "fadr": True, "lyrics": True},
            "source": {"youtube_url": "https://old.invalid"},
            "lyrics": {"synced": True, "lines": [{"text": "old"}]},
            "chords": [{"chord": "Wrong"}],
            "chart": {"url": "https://old.invalid/chart"},
            "slot_overrides": {"guitar.wav": "GTR1"},
            "label_overrides": {"GTR1": "Lead Guitar"},
        }
        with tempfile.TemporaryDirectory() as td, \
                patch.object(server.ji, "load_config",
                             return_value={"jobs_dir": td}), \
                patch.object(server.ji, "load_job", return_value=old), \
                patch.object(server.ji, "save_job") as save, \
                patch.object(server.ji, "stage_download") as download, \
                patch.object(server.ji, "stage_fadr") as fadr, \
                patch.object(server.ji, "stage_chords") as chords, \
                patch.object(server.ji, "stage_lyrics") as lyrics, \
                patch.object(server.ji, "stage_lyrics_align") as align, \
                patch.object(server, "build_review", return_value={"stems": []}):
            server.STATE.update({"state": "preparing", "operation": "import",
                                 "song": "Band - Song", "log": [],
                                 "summary": "", "review": None})
            server.BUSY.acquire()
            server.run_prepare("https://new.invalid", "Band", "Song", True)

        rebuilt = save.call_args_list[0].args[1]
        self.assertEqual(rebuilt["slot_overrides"], old["slot_overrides"])
        self.assertEqual(rebuilt["label_overrides"], old["label_overrides"])
        self.assertNotIn("lyrics", rebuilt)
        self.assertNotIn("chords", rebuilt)
        self.assertNotIn("chart", rebuilt)
        self.assertEqual(rebuilt["source"]["youtube_url"],
                         "https://new.invalid")
        for stage in (download, fadr, chords, lyrics, align):
            self.assertTrue(stage.call_args.args[-1])
        self.assertEqual(server.STATE["state"], "review")

    def test_partial_download_still_counts_as_cached_recording(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "source.wav").write_bytes(b"recording")
            self.assertFalse(server.job_has_audio(folder))
            self.assertTrue(server.job_has_cached_audio(folder))

    def test_browser_has_single_completion_and_reset_path(self):
        html = (TOOLS / "importer.html").read_text(encoding="utf-8")
        self.assertIn('id="receiptCard"', html)
        self.assertIn("function resetReadyState()", html)
        self.assertIn("function showReceipt(", html)
        self.assertIn("function stopPolling()", html)
        self.assertIn("Song re-added to REAPER", html)
        self.assertNotIn("setTimeout(loadSongs, 600)", html)

    def test_server_tracks_named_operations_and_acknowledgement(self):
        source = Path(server.__file__).read_text(encoding="utf-8")
        self.assertIn('"operation": "import"', source)
        self.assertIn('"operation": "import_library"', source)
        self.assertIn('"operation": "readd"', source)
        self.assertIn('self.path == "/api/ack"', source)
        self.assertIn('"code": "cached_recording"', source)


if __name__ == "__main__":
    unittest.main()
