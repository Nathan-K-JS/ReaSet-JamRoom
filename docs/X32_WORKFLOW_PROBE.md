# X32 workflow acceptance probes

These are standalone, explicitly authorized hardware acceptance tools in the
development worktree. They are not a deployed ReaSet mixer bridge. They never
access REAPER, the live library, recording files or importer endpoints.

Firmware updates, factory resets, boot/service commands, network settings and
clock changes are excluded. Nathan explicitly ruled out firmware work. Ordinary
development permission does not authorize running these hardware write probes.

## Scope and recovery

`tools/x32_workflow_probe.py` requires unnamed channels 13-16 with all faders
and sends at minimum, processing bypassed and pairs unlinked. It captures a fresh
2,125-group desk baseline and exact typed scalars before writing. It mutes these
spares, removes their main assignments and selects source OFF. It then tests
individual source selection, link/unlink of 13/14, and two dummy four-strip
profiles (BAND and QUARTET) with different EQ, compression, fader and send values.
These profiles are control tests, not recommended musical presets.

The stereo test requires matching processing settings on 13/14 before linking.
It records link side effects and restores pan values after unlinking. It does
not establish that every subsequent OSC write automatically propagates to the
linked partner; that behaviour needs an explicit paired-control test.

`tools/x32_fx_workflow_probe.py` requires unused FX1 in the observed AMP/INS
configuration, no selected FX1 insert anywhere, no finite FX1-return bus sends
and the inspected output-source range. It mutes FX1 returns before testing
Mix13 sources and Hall, Room and Plate algorithms, including predelay and decay
controls. It restores the original algorithm, its active parameters and sources
before restoring the return mutes. No existing vocal sends are changed.

`tools/x32_unplugged_input_probe.py` is a separate, more restrictive probe for
physical local XLR13 only. Nathan explicitly confirmed that socket is unplugged.
It verifies the headamp mapping, disconnects/mutes spare channel13, tests a
0dB to +0.5dB gain change and phantom OFF/ON/OFF, then restores the headamp before
reconnecting the channel. This confirmation applies to this supervised session;
future runs need fresh physical confirmation. The console readback proves the
control state; it is not an electrical measurement of 48V at the socket.

Both tools use separate UDP write and query sockets. Every changed value must
read back independently. A durable journal records originals and pending intent
before each write. Cleanup restores only the captured scope, verifies typed
scalars, and compares the complete desk snapshot. Neither tool recalls a scene.
Network/process failure can interrupt cleanup: inspect the journal and recover
the affected scope. An unexpected current value stops automatic restoration to
avoid overwriting another operator's change. These are supervised probes, not
an unattended transaction service; OSC has no atomic compare-and-set operation.

## Protocol findings

- Faders read back on a 1/1023 normalized grid. Bus sends do not use that same
  grid. The first expanded run halted when a send rounded 512/1023 to 0.5.
  Only the isolated spares remained changed; scoped recovery restored all typed
  values. The corrected probe rejects that send value before sending and uses
  exact quarter values for its limited send tests. This is not a general dB codec.
- FX parameter types depend on the algorithm. AMP parameter 9 is an integer;
  the corresponding reverb parameter is a float. Inactive AMP parameter 10
  returned NaN. Never replay all 64 parameter queries blindly. Capture active
  typed values, restore the original algorithm first, then its parameters, and
  compare the full FX group before reconnecting returns.

Parameter identities and algorithm enums were checked against the protocol
researcher's [channel definitions](https://github.com/pmaillot/X32-Behringer/blob/master/X32Channel.h),
[configuration definitions](https://github.com/pmaillot/X32-Behringer/blob/master/X32CfgMain.h)
and [FX implementation](https://github.com/pmaillot/X32-Behringer/blob/master/X32.c).
Actual hardware readback, not an emulator, is the acceptance evidence.

## Meaningful limits

These silent tests establish control/readback and restoration, not audio quality,
feedback safety at performance levels, cable identity, or complete scene recovery.
Phantom needs a physically unplugged socket confirmed by the operator. Only the
separate unplugged-input probe permits physical gain/phantom writes, restricted
to XLR13. Global I/O banks, console scene store/recall and REAPER recording-route
changes remain outside all these probes' write scope.

Guitar 1 currently occupies channel 6; channel 5 is Bass and channel 7 is Guitar 2.
An X32 link uses an odd/even pair, so a stereo Guitar 1 design must allocate a
pair and a second confirmed physical input rather than link arbitrary 6/7.
The existing vocal effect is FX2 Plate from bus14, with a finite send observed
only on vocal1. A four-vocal reverb workflow must choose whether to extend that
effect or allocate another free engine, then establish the desired IEM returns.
Changing the real instruments or REAPER recording layout is a separate operation.

Offline checks (no sockets):

```powershell
python -m unittest discover -s tools -p test_x32*probe.py -v
```

Evidence is stored outside the live installation under
`Documents\JamRoom Inspections\2026-09-27-X32-workflow-proof`.
Retain the first interrupted run as history; later verified runs and the final
cross-run comparison determine current restoration status.

## 27 September 2026 results

- Channels 13-16: source selectors, mute/main assignment isolation, stereo
  link/unlink, EQ and compressor changes, faders and FX-bus sends passed.
  Both dummy BAND and QUARTET profiles read back as requested. The desk adjusted
  main and send pans when linking/unlinking; these side effects were captured.
- FX1: Hall, Room and Plate selection, Mix13 L/R sources, predelay and decay
  writes passed. Original AMP parameters and return state were restored.
- Physically unplugged local XLR13: +0.5dB gain read back, then returned to 0dB;
  phantom ON read back, then returned to OFF before channel reconnection.
- Seventeen offline guard/recovery tests passed, including applied-write/lost-
  reply failures, concurrent edits, typed FX restoration and phantom cleanup.

The final evidence report records full-desk and protected-file comparisons.
No console scene was stored or recalled, and no musical preset was applied to
the working inputs. The first send-quantization interruption and scoped recovery
remain documented alongside the corrected successful run.
