import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from x32_fx_workflow_probe import PARAMS, RETURNS, SOURCES, TYPE, fx_proof, guard


class FakeFX:
    def __init__(self, fail=False):
        self.values = {TYPE: 56, **{p: 0 for p in SOURCES},
                       **{p: 1 for p in RETURNS}, **{p: .7 for p in PARAMS}}
        self.values[PARAMS[-1]] = 1
        self.fail = fail

    def scalar(self, a, typ):
        return self.values[a]

    def request(self, a):
        value = self.values[a]
        return ('i' if type(value) is int else 'f'), [value]

    def write(self, a, typ, value):
        self.values[a] = value
        if a == TYPE:
            self.values.update({p: .25 for p in PARAMS})
            self.values[PARAMS[-1]] = 0 if value == 56 else .5
        if a == PARAMS[1] and self.fail and self.values[TYPE] != 56:
            self.fail = False
            raise TimeoutError('lost applied FX parameter response')

    def node(self, p):
        if p == 'fx/1':
            return '/fx/1 ' + {56: 'AMP', 0: 'HALL', 3: 'ROOM', 5: 'PLAT'}[self.values[TYPE]]
        if p == 'fx/1/source':
            return '/fx/1/source ' + ' '.join('INS' if self.values[a] == 0 else 'MIX13' for a in SOURCES)
        return '/fx/1/par ' + repr([self.values[a] for a in PARAMS])


class FXTests(unittest.TestCase):
    def test_used_insert_and_return_send_rejected(self):
        baseline = {'fx/1': '/fx/1 AMP', 'fx/1/source': '/fx/1/source INS INS'}
        guard(baseline)
        for extra in [{'ch/06/insert': '/ch/06/insert OFF PRE FX1L'},
                      {'fxrtn/01/mix/01': '/fxrtn/01/mix/01 ON -10.0 -100 POST 0'},
                      {'outputs/main/01': '/outputs/main/01 66 POST OFF'}]:
            with self.assertRaises(RuntimeError):
                guard({**baseline, **extra})

    def test_algorithms_and_typed_original_restore(self):
        for fail in [False, True]:
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as d:
                c = FakeFX(fail)
                before = dict(c.values)
                nodes = {p: c.node(p) for p in ['fx/1', 'fx/1/source', 'fx/1/par']}
                with contextlib.redirect_stdout(io.StringIO()):
                    if fail:
                        with self.assertRaises(TimeoutError):
                            fx_proof(c, Path(d), nodes)
                    else:
                        fx_proof(c, Path(d), nodes)
                self.assertEqual(c.values, before)
                self.assertIs(type(c.values[PARAMS[-1]]), int)


if __name__ == '__main__':
    unittest.main()
