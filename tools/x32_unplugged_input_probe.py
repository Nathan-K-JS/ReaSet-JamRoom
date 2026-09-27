"""XLR13-only phantom/gain proof after explicit physical-unplugged confirmation.

Never infer the physical socket from a channel label. This standalone probe
requires the exact observed local routing and isolated spare channel13.
"""
import argparse
import json
import time
from pathlib import Path

from x32_capability_probe import equal, snapshot
from x32_workflow_probe import SCHEMA, Transaction, WorkflowClient, durable


PHANTOM = '/headamp/012/phantom'
GAIN = '/headamp/012/gain'
CHANNEL = ['/ch/13/mix/on', '/ch/13/mix/st', '/ch/13/config/source']


class InputClient(WorkflowClient):
    def write(self, address, typ, value):
        if address == PHANTOM:
            if typ != 'i' or type(value) is not int or value not in (0, 1):
                raise ValueError('Invalid phantom enum')
        elif address == GAIN:
            if typ != 'f' or not any(equal(value, v) for v in [24/144, 25/144]):
                raise ValueError('Only original 0dB and test +0.5dB permitted')
        elif address not in CHANNEL:
            raise ValueError('Outside confirmed socket scope')
        super().write(address, typ, value)


def input_proof(c, folder, nodes, confirmed_input, settle=time.sleep):
    if confirmed_input != 13:
        raise RuntimeError('Physical unplugged socket 13 confirmation is required')
    if nodes['headamp/012'] != '/headamp/012 +0.0 OFF':
        raise RuntimeError('Expected physical gain/phantom baseline changed')
    if c.scalar('/config/chlink/13-14', 'i') != 0:
        raise RuntimeError('Channel13 is linked')
    if c.scalar('/ch/13/config/name', 's') != '' or c.scalar('/ch/13/config/source', 'i') != 13:
        raise RuntimeError('Channel13 is not the inspected spare')
    if c.scalar('/ch/13/mix/fader', 'f') != 0 or any(
            c.scalar(f'/ch/13/mix/{b:02}/level', 'f') != 0 for b in range(1, 17)):
        raise RuntimeError('Spare has active levels')
    mapping = {str(i): c.scalar(f'/-ha/{i:02}/index', 'i') for i in range(40)}
    durable(folder / 'headamp-mapping.json', mapping)
    if [i for i, v in mapping.items() if v == 12] != ['12']:
        raise RuntimeError('Physical XLR13 has unexpected channel consumers')
    SCHEMA.update({PHANTOM: 'i', GAIN: 'f'})
    t = Transaction(c, folder, CHANNEL + [PHANTOM, GAIN])
    try:
        for a in CHANNEL:
            t.set(a, 0)
        t.set(GAIN, 25/144)
        durable(folder / 'gain-test.json', {'node': c.node('headamp/012')})
        t.set(GAIN, t.before[GAIN])
        t.set(PHANTOM, 1)
        settle(5)
        if c.scalar(PHANTOM, 'i') != 1:
            raise RuntimeError('Phantom ON did not remain verified')
        durable(folder / 'phantom-on.json', {'node': c.node('headamp/012'),
                'confirmation': 'User confirmed local XLR13 physically unplugged'})
        print('PASS XLR13 +0.5dB gain and phantom ON readback', flush=True)
    finally:
        t.set(PHANTOM, t.before[PHANTOM])
        settle(5)
        t.set(GAIN, t.before[GAIN])
        if c.node('headamp/012') != nodes['headamp/012']:
            raise RuntimeError('Physical input restoration differs; channel stays isolated')
        t.restore_fields(CHANNEL)
        t.verify()
        print('PASS XLR13 phantom OFF, gain and channel restored', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ip', required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--confirmed-unplugged-input', type=int, choices=[13], required=True)
    p.add_argument('--write-proof', action='store_true')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = list(json.loads(args.baseline.read_text())['nodes'])
    with (args.output / 'wire.jsonl').open('w') as log:
        c = InputClient(args.ip, log)
        before = None
        try:
            tags, identity = c.request('/xinfo')
            if tags != 'ssss' or identity[:3] != [args.ip, 'X32RACK-0E-2F-85', 'X32RACK']:
                raise RuntimeError('Wrong mixer')
            durable(args.output / 'identity.json', identity)
            before = snapshot(c, paths, args.output / 'before.json')
            if args.write_proof:
                input_proof(c, args.output, before, args.confirmed_unplugged_input)
        finally:
            try:
                if before is not None and args.write_proof:
                    after = snapshot(c, paths, args.output / 'after.json')
                    diff = {k: {'before': v, 'after': after[k]} for k, v in before.items() if v != after[k]}
                    durable(args.output / 'comparison.json', diff)
                    print('Full snapshot differences:', len(diff), flush=True)
                    if diff:
                        raise RuntimeError('Full snapshot restoration differs')
            finally:
                c.close()


if __name__ == '__main__':
    main()
