import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from x32_unplugged_input_probe import CHANNEL, GAIN, PHANTOM, InputClient, input_proof
from x32_workflow_probe import SCHEMA


class FakeInput:
    def __init__(self, fail=False):
        self.values = {CHANNEL[0]: 1, CHANNEL[1]: 1, CHANNEL[2]: 13,
                       GAIN: 24/144, PHANTOM: 0, '/config/chlink/13-14': 0,
                       '/ch/13/config/name': '', '/ch/13/mix/fader': 0.0}
        self.values.update({f'/ch/13/mix/{b:02}/level': 0.0 for b in range(1, 17)})
        self.fail, self.writes = fail, []

    def scalar(self, a, typ):
        if a.startswith('/-ha/'):
            return 12 if a == '/-ha/12/index' else -1
        return self.values[a]

    def write(self, a, typ, value):
        self.values[a] = value
        self.writes.append((a, value))
        if a == PHANTOM and value == 1 and self.fail:
            self.fail = False
            raise TimeoutError('lost phantom ON response')

    def node(self, p):
        return f"/headamp/012 +{self.values[GAIN]*72-12:.1f} " + ('ON' if self.values[PHANTOM] else 'OFF')


class InputTests(unittest.TestCase):
    def test_missing_physical_confirmation_blocks_all_writes(self):
        c = FakeInput()
        with self.assertRaisesRegex(RuntimeError, 'confirmation'):
            input_proof(c, Path('.'), {}, None)
        self.assertEqual(c.writes, [])

    def test_other_sockets_and_large_gain_rejected(self):
        c = InputClient.__new__(InputClient)
        for a, typ, value in [('/headamp/013/phantom', 'i', 1),
                              (GAIN, 'f', 1), ('/ch/14/mix/on', 'i', 0)]:
            with self.assertRaises(ValueError):
                c.write(a, typ, value)

    def test_phantom_off_before_source_restore_even_after_failure(self):
        saved_schema = dict(SCHEMA)
        try:
            for fail in [False, True]:
                with self.subTest(fail=fail), tempfile.TemporaryDirectory() as d:
                    c = FakeInput(fail)
                    before = dict(c.values)
                    nodes = {'headamp/012': c.node('headamp/012')}
                    with contextlib.redirect_stdout(io.StringIO()):
                        if fail:
                            with self.assertRaises(TimeoutError):
                                input_proof(c, Path(d), nodes, 13, settle=lambda _: None)
                        else:
                            input_proof(c, Path(d), nodes, 13, settle=lambda _: None)
                    self.assertEqual(c.values, before)
                    self.assertLess(c.writes.index((PHANTOM, 0)), c.writes.index((CHANNEL[2], 13)))
        finally:
            SCHEMA.clear()
            SCHEMA.update(saved_schema)


if __name__ == '__main__':
    unittest.main()
