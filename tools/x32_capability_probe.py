"""Bounded X32 hardware proof, not a general mixer controller or restore tool.

No REAPER interaction. Snapshot mode is read-only. Explicit --write-proof tests
display metadata and bypassed channel-13 parameters, immediately restoring each.
Never sends routing, preamp, phantom, scene, firmware, clock or transport writes.
"""
import argparse
import datetime as dt
import json
import math
import os
import re
import socket
import struct
import time
from pathlib import Path


STRIPS = ([f"ch/{i:02}" for i in range(1, 33)]
          + [f"{kind}/{i:02}" for kind, count in
             [("auxin", 8), ("fxrtn", 8), ("bus", 16), ("mtx", 6)]
             for i in range(1, count + 1)]
          + [f"dca/{i}" for i in range(1, 9)] + ["main/st", "main/m"])
METADATA = {f"/{s}/config/{field}": typ for s in STRIPS
            for field, typ in [("name", "s"), ("color", "i")]}
PASSIVE = {
    "/ch/13/eq/1/g": ("f", "eq", 0.55),
    "/ch/13/eq/1/f": ("f", "eq", 0.50),
    # Q has 72 steps, including the endpoints; 0.5 is not representable.
    "/ch/13/eq/1/q": ("f", "eq", 35 / 71),
    "/ch/13/eq/1/type": ("i", "eq", 0),
    "/ch/13/gate/thr": ("f", "gate", 0.25),
    "/ch/13/gate/filter/on": ("i", "gate", 1),
    "/ch/13/dyn/thr": ("f", "dyn", 0.50),
    "/ch/13/dyn/ratio": ("i", "dyn", 3),
}
NODE = re.compile(r"(?:config|ch|auxin|fxrtn|bus|mtx|main|dca|fx|outputs|headamp|-prefs)(?:/[A-Za-z0-9_-]+)*\Z")


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def osc_string(value):
    if "\0" in value:
        raise ValueError("Embedded NUL")
    raw = value.encode("utf-8") + b"\0"
    return raw + b"\0" * (-len(raw) % 4)


def packet(address, typ=None, value=None):
    data = osc_string(address)
    if typ:
        data += osc_string("," + typ)
        data += osc_string(value) if typ == "s" else struct.pack(">" + typ, value)
    return data


def decode(data):
    def string(pos):
        end = data.index(0, pos)
        return data[pos:end].decode("utf-8"), (end + 4) & ~3
    address, pos = string(0)
    tags, pos = string(pos)
    if not tags.startswith(","):
        raise ValueError("Missing OSC tags")
    values = []
    for typ in tags[1:]:
        if typ == "s":
            value, pos = string(pos)
        elif typ in "if":
            value = struct.unpack_from(">" + typ, data, pos)[0]
            pos += 4
        else:
            raise ValueError("Unsupported OSC type " + typ)
        values.append(value)
    return address, tags[1:], values


def equal(a, b):
    return math.isclose(a, b, abs_tol=1e-5, rel_tol=0) if isinstance(a, float) else a == b


def validate_write(address, typ, value):
    allowed = METADATA.get(address) or (PASSIVE[address][0] if address in PASSIVE else None)
    if typ != allowed:
        raise ValueError("Write outside fixed allowlist: " + address)
    if typ == "s" and (not isinstance(value, str) or "\0" in value or len(value.encode()) > 12):
        raise ValueError("Invalid display name")
    if typ == "f" and (not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError("Invalid normalized value")
    if address == "/ch/13/eq/1/q" and not math.isclose(value * 71, round(value * 71), abs_tol=1e-4, rel_tol=0):
        raise ValueError("Q must use a supported step n/71")
    if typ == "i":
        limit = 15 if address in METADATA else {"type": 5, "on": 1, "ratio": 11}[address.rsplit("/", 1)[1]]
        if type(value) is not int or not 0 <= value <= limit:
            raise ValueError("Invalid enum")


class Client:
    def __init__(self, ip, log):
        self.peer = (ip, 10023)
        self.log = log
        self.reader = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.reader.bind(("0.0.0.0", 0))
        self.reader.settimeout(0.4)
        self.writer = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.writer.bind(("0.0.0.0", 0))

    def record(self, **data):
        self.log.write(json.dumps({"utc": now(), **data}) + "\n")
        self.log.flush()

    def request(self, address, typ=None, value=None):
        # Writer echoes cannot reach this separate observer socket.
        raw = packet(address, typ, value)
        for attempt in range(3):
            self.reader.setblocking(False)
            try:
                while True:
                    self.reader.recvfrom(16384)
            except BlockingIOError:
                pass
            finally:
                self.reader.settimeout(0.4)
            self.record(kind="query", address=address, packet=raw.hex())
            self.reader.sendto(raw, self.peer)
            end = time.monotonic() + 0.7
            while time.monotonic() < end:
                try:
                    data, peer = self.reader.recvfrom(16384)
                except socket.timeout:
                    break
                if peer != self.peer:
                    continue
                addr, tags, values = decode(data)
                if address == "/node":
                    match = addr in ("node", "/node") and tags == "s" and values[0].split()[0] == "/" + value
                else:
                    match = addr == address
                if match:
                    self.record(kind="reply", address=addr, types=tags, values=values)
                    return tags, values
            time.sleep(0.05)
        raise TimeoutError(address + " " + str(value))

    def scalar(self, address, expected_type):
        typ, values = self.request(address)
        if typ != expected_type or len(values) != 1:
            raise ValueError("Unexpected parameter type: " + address)
        return values[0]

    def node(self, path):
        if not NODE.fullmatch(path):
            raise ValueError("Node outside read allowlist")
        return self.request("/node", "s", path)[1][0].rstrip("\n")

    def write(self, address, typ, value):
        validate_write(address, typ, value)
        raw = packet(address, typ, value)
        self.record(kind="write", address=address, types=typ, value=value, packet=raw.hex())
        self.writer.sendto(raw, self.peer)
        time.sleep(0.08)

    def close(self):
        self.reader.close()
        self.writer.close()


def snapshot(client, paths, target):
    nodes = {}
    for i, path in enumerate(paths):
        nodes[path] = client.node(path)
        time.sleep(0.035)
        if (i + 1) % 500 == 0:
            print("Snapshot", target.name, i + 1, "/", len(paths), flush=True)
    target.write_text(json.dumps({"utc": now(), "nodes": nodes}, indent=2), encoding="utf-8")
    return nodes


def assert_passive(client, section):
    if client.scalar(f"/ch/13/{section}/on", "i") != 0:
        raise RuntimeError("Channel 13 processing is no longer bypassed")
    if client.scalar("/ch/13/mix/fader", "f") != 0:
        raise RuntimeError("Channel 13 fader is no longer at -infinity")
    for i in range(1, 17):
        if client.scalar(f"/ch/13/mix/{i:02}/level", "f") != 0:
            raise RuntimeError("Channel 13 send is no longer at -infinity")


def prove(client, address, typ, alternate, folder):
    before = client.scalar(address, typ)
    validate_write(address, typ, before)
    validate_write(address, typ, alternate)
    if equal(before, alternate):
        raise RuntimeError("Test value must differ from original")
    group = address.lstrip("/").rsplit("/", 1)[0]
    group_before = client.node(group)
    row = {"address": address, "type": typ, "before": before, "test": alternate,
           "group_before": group_before, "started": now(), "restored": False}
    journal = folder / "pending.json"
    with journal.open("w", encoding="utf-8") as pending:
        pending.write(json.dumps(row, indent=2))
        pending.flush()
        os.fsync(pending.fileno())
    try:
        client.write(address, typ, alternate)
        actual = client.scalar(address, typ)
        row["read_back"] = actual
        if not equal(actual, alternate):
            raise RuntimeError("Changed value did not verify: " + address)
        row["group_during"] = client.node(group)
        if row["group_during"] == group_before:
            raise RuntimeError("Independent grouped read did not change")
    finally:
        current = client.scalar(address, typ)
        if not equal(current, before):
            if not equal(current, alternate):
                raise RuntimeError("Unexpected concurrent value; pending journal retained: " + address)
            for attempt in range(3):
                client.write(address, typ, before)
                if equal(client.scalar(address, typ), before):
                    break
            else:
                raise RuntimeError("RESTORE UNCONFIRMED: " + address)
        row["group_after"] = client.node(group)
        row["restored"] = row["group_after"] == group_before
        with (folder / "results.jsonl").open("a", encoding="utf-8") as results:
            results.write(json.dumps(row) + "\n")
        if not row["restored"]:
            raise RuntimeError("Grouped restore differs: " + address)
        journal.write_text(json.dumps({"pending": False, "last_restored": address}), encoding="utf-8")
    print("PASS restored", address, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", required=True)
    parser.add_argument("--expected-name", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--write-proof", action="store_true")
    parser.add_argument("--passive-only", action="store_true", help="Skip previously proven metadata cycles")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    template = json.loads(args.baseline.read_text(encoding="utf-8"))["nodes"]
    with (args.output / "wire.jsonl").open("x", encoding="utf-8") as log:
        client = Client(args.ip, log)
        try:
            tags, identity = client.request("/xinfo")
            if tags != "ssss" or identity[:3] != [args.ip, args.expected_name, "X32RACK"]:
                raise RuntimeError("Mixer identity mismatch")
            (args.output / "identity.json").write_text(json.dumps(identity), encoding="utf-8")
            before = snapshot(client, list(template), args.output / "before.json")
            if not args.write_proof:
                return
            # First prove one unused-channel string and one enum before expanding.
            order = ["/ch/13/config/name", "/ch/13/config/color"]
            order += [p for p in METADATA if p not in order]
            if args.passive_only:
                order = []
            for address in order:
                typ = METADATA[address]
                current = client.scalar(address, typ)
                alternate = ("JR_PROBE" if current != "JR_PROBE" else "JR_PROBE2") if typ == "s" else current ^ 1
                prove(client, address, typ, alternate, args.output)
            for address, (typ, section, alternate) in PASSIVE.items():
                assert_passive(client, section)
                current = client.scalar(address, typ)
                if equal(current, alternate):
                    alternate = (36 / 71 if address.endswith("/eq/1/q") else
                                 (0 if typ == "i" and alternate else (1 if typ == "i" else 0.4)))
                prove(client, address, typ, alternate, args.output)
                assert_passive(client, section)
        finally:
            # Full observation even after a failed proof; never bulk-restore a scene.
            if "before" in locals() and args.write_proof:
                after = snapshot(client, list(template), args.output / "after.json")
                changes = {p: {"before": v, "after": after[p]} for p, v in before.items() if v != after[p]}
                (args.output / "comparison.json").write_text(json.dumps(changes, indent=2), encoding="utf-8")
                print("Full snapshot differences:", len(changes), flush=True)
            client.close()


if __name__ == "__main__":
    main()
