"""Explicitly authorized, silent X32 workflow proof. No REAPER or firmware API.

Fixed resources: spare ch13-16, link13/14, unused FX1 and its returns.
Never recalls a console scene or touches physical preamps, global routing,
network, clock, firmware, or any live ch1-12/17-32 parameter.
"""
import argparse
import json
import math
import os
import time
from pathlib import Path

from x32_capability_probe import Client, equal, now, packet, snapshot


LINK = '/config/chlink/13-14'
SCHEMA = {}
for ch in range(13, 17):
    root = f'/ch/{ch:02}'
    fields = {'config/name': 's', 'config/source': 'i', 'mix/on': 'i',
              'mix/fader': 'f', 'mix/st': 'i', 'mix/pan': 'f',
              'eq/on': 'i', 'eq/1/g': 'f', 'dyn/on': 'i',
              'dyn/thr': 'f', 'dyn/ratio': 'i'}
    for bus in range(1, 17):
        fields[f'mix/{bus:02}/on'] = 'i'
        fields[f'mix/{bus:02}/level'] = 'f'
        if bus % 2:
            fields[f'mix/{bus:02}/pan'] = 'f'
    SCHEMA.update({f'{root}/{p}': typ for p, typ in fields.items()})
SCHEMA[LINK] = 'i'
SCHEMA.update({'/fx/1/type': 'i', '/fx/1/source/l': 'i', '/fx/1/source/r': 'i'})
for n in range(1, 65):
    SCHEMA[f'/fx/1/par/{n:02}'] = 'f'
for n in [1, 2]:
    SCHEMA[f'/fxrtn/{n:02}/mix/on'] = 'i'


def validate(address, typ, value):
    if SCHEMA.get(address) != typ:
        raise ValueError('Outside fixed workflow scope: ' + address)
    if typ == 's':
        if not isinstance(value, str) or '\0' in value or len(value.encode()) > 12:
            raise ValueError('Invalid name')
    elif typ == 'f':
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Invalid normalized value')
        if address.startswith('/ch/') and address.endswith('/level') and value not in (0, .25, .5, 1):
            raise ValueError('Send proof only permits verified endpoint/quarter values')
        if address.endswith('/mix/fader') and not math.isclose(value * 1023, round(value * 1023), abs_tol=1e-4):
            raise ValueError('Fader must use a supported step n/1023')
    else:
        limit = 64 if address.endswith('/config/source') else (
            60 if address == '/fx/1/type' else (
                16 if address.startswith('/fx/1/source/') else (
                    11 if address.endswith('/dyn/ratio') else 1)))
        if type(value) is not int or not 0 <= value <= limit:
            raise ValueError('Invalid enum')


def durable(path, data):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temporary.replace(path)


class WorkflowClient(Client):
    def write(self, address, typ, value):
        validate(address, typ, value)
        raw = packet(address, typ, value)
        self.record(kind='write', address=address, types=typ, value=value, packet=raw.hex())
        self.writer.sendto(raw, self.peer)
        time.sleep(0.12)


class Transaction:
    def __init__(self, client, folder, addresses):
        self.c, self.folder = client, folder
        self.before = {a: client.scalar(a, SCHEMA[a]) for a in addresses}
        for a, v in self.before.items():
            validate(a, SCHEMA[a], v)
        self.expected = dict(self.before)
        self.events = []
        self.pending = None
        self.save()

    def save(self, restored=False):
        durable(self.folder / 'journal.json', dict(utc=now(), before=self.before,
                expected=self.expected, pending=self.pending, events=self.events,
                restored=restored))

    def set(self, address, value):
        typ = SCHEMA[address]
        validate(address, typ, value)
        current = self.c.scalar(address, typ)
        if not equal(current, self.expected[address]):
            raise RuntimeError('Concurrent change: ' + address)
        if equal(current, value):
            return
        self.pending = {'address': address, 'before': current, 'requested': value}
        self.save()
        # Record intent before UDP send, allowing recovery after a lost reply.
        self.expected[address] = value
        self.c.write(address, typ, value)
        actual = self.c.scalar(address, typ)
        if not equal(actual, value):
            raise RuntimeError(f'Unexpected readback {address}: {actual} != {value}')
        self.events.append(dict(address=address, before=current, after=actual))
        self.pending = None
        self.save()

    def observe_side_effects(self, addresses, reason):
        # Only used immediately after stereo-link and FX-algorithm operations,
        # with their explicitly bounded side-effect fields captured beforehand.
        for a in addresses:
            value = self.c.scalar(a, SCHEMA[a])
            if not equal(value, self.expected[a]):
                self.events.append(dict(address=a, before=self.expected[a],
                                        after=value, side_effect=reason))
                self.expected[a] = value
        self.save()

    def restore_fields(self, addresses):
        for a in addresses:
            self.set(a, self.before[a])

    def verify(self):
        differences = {a: {'before': v, 'after': self.c.scalar(a, SCHEMA[a])}
                       for a, v in self.before.items()}
        differences = {a: v for a, v in differences.items() if not equal(v['before'], v['after'])}
        durable(self.folder / 'scalar-comparison.json', differences)
        if differences:
            raise RuntimeError('Scalar restoration differs: ' + str(differences))
        self.save(restored=True)


def assert_spares(c, nodes):
    if c.scalar(LINK, 'i') != 0 or c.scalar('/config/chlink/15-16', 'i') != 0:
        raise RuntimeError('Spare channels already linked')
    for ch in range(13, 17):
        root = f'/ch/{ch:02}'
        if c.scalar(root + '/config/name', 's') != '':
            raise RuntimeError('Spare channel is named')
        if c.scalar(root + '/mix/fader', 'f') != 0:
            raise RuntimeError('Spare fader is in use')
        for bus in range(1, 17):
            if c.scalar(root + f'/mix/{bus:02}/level', 'f') != 0:
                raise RuntimeError('Spare send is in use')
        for section in ['eq', 'dyn', 'gate', 'insert']:
            if c.scalar(root + f'/{section}/on', 'i') != 0:
                raise RuntimeError('Spare processing in use')
    # Identical ch13/14 processing makes link-copy side effects bounded.
    for p, value in nodes.items():
        if p.startswith('ch/13/') and p != 'ch/13/config':
            peer = p.replace('ch/13/', 'ch/14/', 1)
            if value.split(' ', 1)[1] != nodes[peer].split(' ', 1)[1]:
                raise RuntimeError('Stereo candidates differ: ' + p)


def isolated(t):
    for ch in range(13, 17):
        for suffix, value in [('config/source', 0), ('mix/on', 0), ('mix/st', 0)]:
            a = f'/ch/{ch:02}/{suffix}'
            if not equal(t.c.scalar(a, SCHEMA[a]), value):
                raise RuntimeError('Silent isolation lost: ' + a)


def channel_proof(c, folder, nodes):
    assert_spares(c, nodes)
    addresses = [a for a in SCHEMA if a.startswith('/ch/') or a == LINK]
    t = Transaction(c, folder, addresses)
    pans = [a for a in addresses if a.endswith('/pan') and a.startswith(('/ch/13/', '/ch/14/'))]
    try:
        for ch in range(13, 17):
            for suffix, value in [('mix/on', 0), ('mix/st', 0), ('config/source', 0)]:
                t.set(f'/ch/{ch:02}/{suffix}', value)
        isolated(t)
        # Routing selectors are exercised with all faders/sends at the floor.
        for ch in range(13, 17):
            t.set(f'/ch/{ch:02}/config/source', 14 if ch == 13 else 13)
            t.set(f'/ch/{ch:02}/config/source', 0)
        isolated(t)
        t.set(LINK, 1)
        t.observe_side_effects(pans, 'link-on')
        durable(folder / 'stereo-linked.json', {p: c.node(p) for p in nodes
                if p == 'config/chlink' or p.startswith(('ch/13/', 'ch/14/'))})
        t.set(LINK, 0)
        t.observe_side_effects(pans, 'link-off')
        t.restore_fields(pans)
        print('PASS stereo link/unlink and source selection', flush=True)
        # Named, scoped configuration changes, never console scene recall.
        for name, gain, threshold, ratio, level in [
                ('BAND', .55, .5, 5, 512/1023),
                ('QUARTET', .5, .625, 3, 384/1023)]:
            isolated(t)
            for ch in range(13, 17):
                root = f'/ch/{ch:02}'
                settings = {'config/name': f'{name} {ch-12}', 'eq/on': 1,
                            'eq/1/g': gain, 'dyn/on': 1, 'dyn/thr': threshold,
                            'dyn/ratio': ratio, 'mix/fader': level,
                            'mix/13/level': .5 if name == 'BAND' else .25,
                            'mix/13/on': 0 if name == 'BAND' else 1}
                for suffix, value in settings.items():
                    t.set(root + '/' + suffix, value)
            durable(folder / (name.lower() + '.json'), {p: c.node(p) for p in nodes
                    if p.startswith(tuple(f'ch/{n}/' for n in range(13, 17)))})
            print('PASS scoped profile', name, flush=True)
    finally:
        # Do not reconnect physical sources until silent baseline is verified.
        if c.scalar(LINK, 'i') != 0:
            t.set(LINK, 0)
            t.observe_side_effects(pans, 'cleanup-unlink')
        deferred = [a for a in addresses if a.endswith(('/config/source', '/mix/on', '/mix/st'))]
        t.restore_fields([a for a in addresses if a not in deferred])
        for ch in range(13, 17):
            root = f'/ch/{ch:02}'
            if c.scalar(root + '/mix/fader', 'f') != 0 or any(
                    c.scalar(root + f'/mix/{b:02}/level', 'f') != 0 for b in range(1, 17)):
                raise RuntimeError('Cannot reconnect: levels not restored')
        t.restore_fields(deferred)
        t.verify()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ip', required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--write-proof', action='store_true')
    args = p.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    paths = list(json.loads(args.baseline.read_text())['nodes'])
    with (args.output / 'wire.jsonl').open('w') as log:
        c = WorkflowClient(args.ip, log)
        before = None
        try:
            tags, identity = c.request('/xinfo')
            if tags != 'ssss' or identity[:3] != [args.ip, 'X32RACK-0E-2F-85', 'X32RACK']:
                raise RuntimeError('Mixer identity mismatch')
            durable(args.output / 'identity.json', identity)
            before = snapshot(c, paths, args.output / 'before.json')
            if args.write_proof:
                channel_proof(c, args.output, before)
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
