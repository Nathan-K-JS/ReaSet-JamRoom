# Bounded X32 hardware capability probe

Follow [the mandatory live workflow](LIVE_JAMROOM_WORKFLOW.md). Hardware writes
require explicit user authorization for this test. This tool is not an application
integration, a general mixer writer, a scene loader or a whole-desk recovery tool.

## Hardware result, 27 September 2026

On firmware 4.13, all 160 metadata parameters across the 80 listed strips and
all eight passive channel-13 parameters passed changed-value/read-back/restore
checks. The final 2,125-group snapshot matched the original pre-write baseline
exactly. The saved REAPER project/configuration, installed app source and supplied scene
backup hashes were unchanged. Seven offline checks passed.

The first Q attempt exposed quantization and required a scoped restoration of
that bypassed parameter; it was not counted as a successful initial cycle.
The corrected test uses the documented 72-step scale. A fresh full snapshot
after recovery and the final snapshot both matched the original baseline.

Detailed device snapshots and packet logs are retained locally under Nathan's
`Documents/JamRoom Inspections/2026-09-27-X32-write-proof` and its `-passive`
companion directory. They are not bundled in the repository or deployed.

The 27 September 2026 test was authorized after Nathan saved a scene backup.
The probe lives in a separate development worktree. It never contacts REAPER,
the importer or their web interfaces, and never changes live installation files.

## Scope

The default mode queries identity and captures the node paths listed in a prior
inspection snapshot. Requests are paced and matched to the expected sender and
address. Unsupported or missing responses fail the operation rather than being
reported as successful coverage.

`--write-proof` additionally performs changed-value/read-back/restore cycles:

- Names and colours on 32 input channels, 8 Aux input strips, 8 FX returns,
  16 buses, 6 matrices, 8 DCAs and stereo/mono mains.
- Eight parameters on channel 13: three EQ floats, EQ type, gate threshold,
  gate-filter enable, dynamics threshold and dynamics ratio. Their parent
  processing blocks must remain bypassed, the channel fader must remain at
  minus infinity and all 16 sends must remain at minus infinity.

These tests exercise string, integer/enum, boolean and normalized float writes.
Every temporary value must differ from the original. Read-back uses a different
UDP socket from the writer, followed by a grouped `/node` read. Each original is
restored and checked before continuing. A fresh full snapshot before and after
the proof identifies differences, without automatically overwriting them.

The fixed write allowlist excludes signal routing, source selectors, levels,
channel mutes, processing-block enables, preamps, phantom power, FX algorithms,
clock/network settings, scene management, actions and firmware operations.
No same-value writes are counted as proof. Success does not prove all mixer
parameters writable, every firmware-specific feature supported, an audible
signal path, or complete scene restoration.

## Offline checks

Run in the development checkout:

```powershell
python -m unittest discover -s tools -p test_x32_capability_probe.py -v
```

These checks have no network or hardware interaction. They cover the write
allowlist, value validation, OSC encoding, successful restoration, restoration
after a failed grouped read, and refusal when processing is active.
They also reject EQ-Q values between its 72 supported steps. The first hardware
run exposed that `0.5` is quantized by firmware 4.13; its original Q was restored
through a scoped recovery, and the probe now uses representable values `n/71`.

## Hardware execution

Do not copy a command with a live mixer IP into routine automated tests. For an
explicitly authorized run, supply `--ip`, `--expected-name`, `--baseline` (a JSON
snapshot with a `nodes` map), and a new `--output` directory outside live storage.
Omitting `--write-proof` is read-only. The output directory must not already exist.
Keep the original scene export independently available. Leave other editors idle
during the short write cycles so that concurrent changes are not mistaken for a
probe result.

## Evidence and interruption

`wire.jsonl` records queries, replies and writes. `results.jsonl` records each
temporary change and its restoration. `pending.json` is flushed to disk before
each write. `before.json`, `after.json` and `comparison.json` contain the full
observation comparison. These snapshots are not full restorable show backups.

The probe attempts restoration in `finally` if a read/check fails. If a parameter
has an unexpected concurrent value, it stops and preserves the pending journal
rather than overwriting an operator's change. A process kill or network outage can
still prevent restoration; do not assume a pending entry is cleared without
checking the desk. Inspect the exact pending parameter and before-value, then
restore only that explicitly authorized target through a known working control.
Do not respond to a failed cosmetic probe with an automatic whole-scene recall.

The protocol types were checked against the author's
[channel definitions](https://github.com/pmaillot/X32-Behringer/blob/master/X32Channel.h)
and corresponding bus, Aux, FX-return, matrix and DCA definitions. The probe is
independently implemented; no downloaded source is executed.
