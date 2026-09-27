"""Silent FX1 algorithm/source proof for the inspected AMP/INS baseline only.

Preserves active AMP parameters with their actual OSC types. Inactive parameter
queries can return NaN; they must never be replayed as normalized floats.
"""
import argparse
import json
from pathlib import Path

from x32_capability_probe import snapshot
from x32_workflow_probe import SCHEMA, Transaction, WorkflowClient, durable


PARAMS = [f'/fx/1/par/{i:02}' for i in range(1, 10)]
RETURNS = ['/fxrtn/01/mix/on', '/fxrtn/02/mix/on']
SOURCES = ['/fx/1/source/l', '/fx/1/source/r']
TYPE = '/fx/1/type'


def guard(nodes):
    if nodes['fx/1'] != '/fx/1 AMP' or nodes['fx/1/source'] != '/fx/1/source INS INS':
        raise RuntimeError('Expected unused AMP/INS slot changed')
    for path, value in nodes.items():
        if path.endswith('/insert') and ('FX1L' in value or 'FX1R' in value):
            raise RuntimeError('FX1 is selected as an insert')
        if path.startswith('outputs/') and path.count('/') == 2 and int(value.split()[1]) > 41:
            raise RuntimeError('Output source needs manual review')
        if path.startswith(('fxrtn/01/mix/', 'fxrtn/02/mix/')):
            if value.split()[2] != '-oo':
                raise RuntimeError('FX1 return has an active send')


def parameter_types(c):
    for a in PARAMS:
        typ, values = c.request(a)
        if len(values) != 1 or typ not in ('i', 'f'):
            raise RuntimeError('Unexpected FX parameter representation')
        SCHEMA[a] = typ


def fx_proof(c, folder, nodes):
    guard(nodes)
    parameter_types(c)
    t = Transaction(c, folder, [TYPE] + SOURCES + PARAMS + RETURNS)
    try:
        t.set(RETURNS[0], 0)
        t.observe_side_effects([RETURNS[1]], 'linked-return-mute')
        t.set(RETURNS[1], 0)
        for source in SOURCES:
            t.set(source, 13)
        for label, algorithm in [('hall', 0), ('room', 3), ('plate', 5)]:
            if any(c.scalar(a, 'i') != 0 for a in RETURNS):
                raise RuntimeError('FX returns no longer isolated')
            t.set(TYPE, algorithm)
            parameter_types(c)
            t.observe_side_effects(PARAMS, 'algorithm-defaults-' + label)
            # Endpoint values avoid any guessed quantization grids.
            for a in PARAMS[:2]:
                t.set(a, 0.0 if t.expected[a] != 0 else 1.0)
            durable(folder / (label + '.json'), {p: c.node(p) for p in ['fx/1', 'fx/1/source', 'fx/1/par']})
            print('PASS silent reverb algorithm, predelay, decay:', label, flush=True)
    finally:
        # Reconnect returns only after original algorithm, active typed parameters
        # and sources have been independently verified.
        t.set(TYPE, t.before[TYPE])
        parameter_types(c)
        t.observe_side_effects(PARAMS, 'restore-algorithm-defaults')
        t.restore_fields(PARAMS)
        t.restore_fields(SOURCES)
        for p in ['fx/1', 'fx/1/source', 'fx/1/par']:
            if c.node(p) != nodes[p]:
                raise RuntimeError('FX restore differs; returns remain muted: ' + p)
        t.set(RETURNS[0], t.before[RETURNS[0]])
        t.observe_side_effects([RETURNS[1]], 'linked-return-restore')
        t.set(RETURNS[1], t.before[RETURNS[1]])
        t.verify()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ip', required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--write-proof', action='store_true')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = list(json.loads(args.baseline.read_text())['nodes'])
    with (args.output / 'wire.jsonl').open('w') as log:
        c = WorkflowClient(args.ip, log)
        before = None
        try:
            tags, identity = c.request('/xinfo')
            if tags != 'ssss' or identity[:3] != [args.ip, 'X32RACK-0E-2F-85', 'X32RACK']:
                raise RuntimeError('Wrong mixer')
            durable(args.output / 'identity.json', identity)
            before = snapshot(c, paths, args.output / 'before.json')
            if args.write_proof:
                fx_proof(c, args.output, before)
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
