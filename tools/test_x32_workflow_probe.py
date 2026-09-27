import json
import tempfile
import unittest
from pathlib import Path
from x32_workflow_probe import Transaction, validate, isolated


class Fake:
    def __init__(self, fail=False):
        self.values = {'/ch/13/mix/fader': 0.0}
        self.fail, self.writes = fail, []

    def scalar(self, address, typ):
        return self.values[address]

    def write(self, address, typ, value):
        self.values[address] = value
        self.writes.append((address, value))
        if self.fail:
            self.fail = False
            raise TimeoutError('Simulated lost response after applied write')


class WorkflowTests(unittest.TestCase):
    def test_reject_protected_targets(self):
        for address in ['/firmware', '/shutdown', '/-action/init', '/headamp/012/phantom',
                        '/config/routing/IN/1-8', '/ch/01/mix/fader', '/fx/2/type',
                        '/load', '/save', '/-prefs/clocksource']:
            with self.assertRaises(ValueError):
                validate(address, 'i', 0)

    def test_type_and_value_guards(self):
        for address, typ, value in [('/ch/13/mix/fader', 'f', float('nan')),
                                    ('/ch/13/mix/fader', 'f', 1.01),
                                    ('/ch/13/mix/13/level', 'f', 512/1023),
                                    ('/ch/13/mix/fader', 'f', .5),
                                    ('/ch/13/mix/on', 'i', 2),
                                    ('/ch/13/mix/on', 'f', 0),
                                    ('/ch/13/config/name', 's', 'bad\0name')]:
            with self.assertRaises(ValueError):
                validate(address, typ, value)

    def test_restore_after_applied_write_loses_reply(self):
        with tempfile.TemporaryDirectory() as d:
            c = Fake(fail=True)
            t = Transaction(c, Path(d), list(c.values))
            with self.assertRaises(TimeoutError):
                t.set('/ch/13/mix/fader', 512/1023)
            pending = json.loads((Path(d) / 'journal.json').read_text())
            self.assertEqual(pending['pending']['requested'], 512/1023)
            t.restore_fields(t.before)
            t.verify()
            self.assertEqual(c.values['/ch/13/mix/fader'], 0)
            self.assertTrue(json.loads((Path(d) / 'journal.json').read_text())['restored'])

    def test_concurrent_edit_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            c = Fake()
            t = Transaction(c, Path(d), list(c.values))
            t.set('/ch/13/mix/fader', 512/1023)
            c.values['/ch/13/mix/fader'] = .2
            with self.assertRaisesRegex(RuntimeError, 'Concurrent'):
                t.restore_fields(t.before)
            self.assertEqual(c.values['/ch/13/mix/fader'], .2)
            self.assertEqual(len(c.writes), 1)

    def test_isolation_requires_all_four_sources_off_and_muted(self):
        c = Fake()
        c.values = {f'/ch/{n}/{s}': 0 for n in range(13, 17)
                    for s in ['config/source', 'mix/on', 'mix/st']}
        class T:
            pass
        t = T()
        t.c = c
        isolated(t)
        c.values['/ch/16/config/source'] = 16
        with self.assertRaisesRegex(RuntimeError, 'isolation'):
            isolated(t)


if __name__ == '__main__':
    unittest.main()
