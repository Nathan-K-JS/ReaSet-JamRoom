#!/usr/bin/env python3
"""Regression tests for the JamRoom timing-repair data contract.

The authoritative interpolator runs inside REAPER's Lua runtime, which is not
available on a normal development machine.  These tests pin its public maths
and exercise the importer's REAPER-web parsing with deterministic fake replies;
the repository verification script also syntax-checks both browser programs.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import jamroom_importer_server as server  # noqa: E402


def mapped_time(t, anchors, duration):
    """Reference model of ReaSet_ChordsLyrics.lua:mapped_relative."""
    if not anchors:
        return max(0, min(duration, t))
    if len(anchors) == 1 or t <= anchors[0][0]:
        delta = anchors[0][1] - anchors[0][0]
    elif t >= anchors[-1][0]:
        delta = anchors[-1][1] - anchors[-1][0]
    else:
        delta = 0
        for (sx, ax), (sy, ay) in zip(anchors, anchors[1:]):
            if sx <= t <= sy:
                f = (t - sx) / max(0.001, sy - sx)
                delta = (ax - sx) + ((ay - sy) - (ax - sx)) * f
                break
    return max(0, min(duration, t + delta))


class TimingMathTests(unittest.TestCase):
    def test_one_checkpoint_is_constant_shift(self):
        anchors = [(10, 11.5)]
        self.assertAlmostEqual(mapped_time(10, anchors, 240), 11.5)
        self.assertAlmostEqual(mapped_time(200, anchors, 240), 201.5)

    def test_two_checkpoints_correct_drift(self):
        anchors = [(10, 10.5), (210, 214.5)]
        self.assertAlmostEqual(mapped_time(110, anchors, 240), 112.5)
        self.assertAlmostEqual(mapped_time(230, anchors, 240), 234.5)

    def test_piecewise_points_limit_local_change(self):
        anchors = [(10, 10), (80, 80), (120, 123), (160, 160), (220, 220)]
        self.assertAlmostEqual(mapped_time(50, anchors, 240), 50)
        self.assertAlmostEqual(mapped_time(120, anchors, 240), 123)
        self.assertAlmostEqual(mapped_time(220, anchors, 240), 220)

    def test_song_boundaries_are_clamped(self):
        self.assertEqual(mapped_time(1, [(1, -3)], 200), 0)
        self.assertEqual(mapped_time(199, [(1, 10)], 200), 200)


class ImporterContractTests(unittest.TestCase):
    def test_project_extstate_checkpoint_counts(self):
        class Reply:
            text = ("PROJEXTSTATE\tReaSetCLRepair\tsong:7:lyrics\t10=11,200=204\n"
                    "PROJEXTSTATE\tReaSetCLRepair\tsong:7:chords\t10=11\n"
                    "PROJEXTSTATE\tReaSetCLRepair\tsong:7:lyrics:reviewed\t1\n"
                    "PROJEXTSTATE\tReaSetCLRepair\tsong:7:chords:reviewed\t1\n"
                    "PROJEXTSTATE\tReaSetCLRepair\tsong:8:lyrics\t\n")

        with patch.object(server.requests, "get", return_value=Reply()):
            states = server._repair_states("http://reaper", [7, 8])
        self.assertEqual(states[7], {"count": 2, "lyrics_reviewed": True,
                                     "chords_reviewed": True})
        self.assertEqual(states[8]["count"], 0)

    def test_replacing_source_timing_clears_old_corrections(self):
        class Reply:
            def raise_for_status(self):
                return None

        with patch.object(server.requests, "get", return_value=Reply()) as get:
            server._clear_repairs("http://reaper", 7, ["lyrics", "chords"])
        url = get.call_args.args[0]
        self.assertIn("song:7:lyrics/", url)
        self.assertIn("song:7:chords/", url)
        self.assertIn("song:7:lyrics:reviewed/", url)

    def test_feature_surfaces_exist(self):
        html = (ROOT / "ReaSet.html").read_text(encoding="utf-8")
        importer = (TOOLS / "importer.html").read_text(encoding="utf-8")
        lua = (ROOT / "Requirements" / "ReaSet_ChordsLyrics.lua").read_text(
            encoding="utf-8")
        self.assertIn('id="timing-repair"', html)
        self.assertIn("This should start now", html)
        self.assertIn('id="tr-precise"', html)
        self.assertIn("Passage view", html)
        self.assertIn("Review or repair", importer)
        self.assertIn('local REPAIR_SEC = "ReaSetCLRepair"', lua)
        self.assertIn("mapped_relative", lua)


if __name__ == "__main__":
    unittest.main()
