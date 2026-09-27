"""Offline safety checks; no network, live service, audio or mixer access."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import x32_capability_probe as probe


class FakeMixer:
    def __init__(self):
        self.value = "Original"
        self.writes = []
        self.fail_group_once = False

    def scalar(self, address, typ):
        return self.value

    def node(self, path):
        if self.fail_group_once and self.value == "JR_PROBE":
            self.fail_group_once = False
            raise TimeoutError("Injected observation failure")
        return "/" + path + " " + self.value

    def write(self, address, typ, value):
        probe.validate_write(address, typ, value)
        self.writes.append(value)
        self.value = value


class SafetyTests(unittest.TestCase):
    def test_dangerous_and_arbitrary_writes_rejected_before_socket(self):
        for path, typ, value in [
            ("/headamp/000/phantom", "i", 1),
            ("/config/routing/IN/1-8", "i", 1),
            ("/ch/13/config/source", "i", 1),
            ("/ch/13/mix/fader", "f", 0.75),
            ("/ch/01/mix/on", "i", 0),
            ("/ch/13/eq/on", "i", 1),
            ("/fx/1/type", "i", 1),
            ("/load", "s", "scene 0"),
            ("/-action/initall", "i", 1),
            ("/-prefs/srate", "i", 0),
            ("/node", "s", "ch/01/mix ON 0.0"),
        ]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                probe.validate_write(path, typ, value)

    def test_types_ranges_and_string_injection(self):
        for path, typ, value in [
            ("/ch/13/config/name", "s", "bad\0name"),
            ("/ch/13/config/name", "s", "x" * 13),
            ("/ch/13/config/color", "i", 16),
            ("/ch/13/config/color", "f", 1.0),
            ("/ch/13/eq/1/g", "f", float("nan")),
            ("/ch/13/eq/1/g", "f", 1.1),
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                probe.validate_write(path, typ, value)

    def test_codec(self):
        for typ, value in [("s", ""), ("s", "JR_PROBE"), ("i", 15), ("f", 0.5)]:
            raw = probe.packet("/test", typ, value)
            self.assertEqual(len(raw) % 4, 0)
            self.assertEqual(probe.decode(raw), ("/test", typ, [value]))
        self.assertEqual(probe.packet("/xinfo"), b"/xinfo\0\0")

    def test_q_quantization_is_validated_before_write(self):
        with self.assertRaises(ValueError):
            probe.validate_write("/ch/13/eq/1/q", "f", 0.5)
        for value in [33 / 71, 35 / 71, 0.4647887349128723]:
            probe.validate_write("/ch/13/eq/1/q", "f", value)

    def test_successful_round_trip_restores(self):
        mixer = FakeMixer()
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            probe.prove(mixer, "/ch/13/config/name", "s", "JR_PROBE", Path(tmp))
            result = json.loads((Path(tmp) / "results.jsonl").read_text())
            self.assertTrue(result["restored"])
        self.assertEqual(mixer.writes, ["JR_PROBE", "Original"])

    def test_exception_after_write_still_restores(self):
        mixer = FakeMixer()
        mixer.fail_group_once = True
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(TimeoutError):
            probe.prove(mixer, "/ch/13/config/name", "s", "JR_PROBE", Path(tmp))
        self.assertEqual(mixer.value, "Original")
        self.assertEqual(mixer.writes, ["JR_PROBE", "Original"])

    def test_active_processing_blocks_passive_test(self):
        mixer = FakeMixer()
        mixer.scalar = lambda address, typ: 1
        with self.assertRaises(RuntimeError):
            probe.assert_passive(mixer, "eq")
        self.assertEqual(mixer.writes, [])


if __name__ == "__main__":
    unittest.main()
