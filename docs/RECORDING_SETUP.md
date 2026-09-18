# Initial recording setup — proposed template

Recording is still being designed. This guide defines the setup to ship with
the feature; no recording tracks have been created by this documentation update.

## Confirmed live input list and default recording tracks

Nathan supplied this live channel list. Preserve these mixer labels and create
the following **14 recording tracks: 12 mono and two stereo**, beneath a
Recording folder. The USB input column is the intended one-to-one recording
patch, to be established/verified during initial setup; it is not a reading of
the mixer's current Card Output routing.

| X32 live channel | Mixer label | REAPER USB input | Recording track | Format |
| --- | --- | --- | --- | --- |
| 01 | Vox 1 | 1 | `REC Vox 1` | Mono |
| 02 | Vox 2 | 2 | `REC Vox 2` | Mono |
| 03 | Vox 3 | 3 | `REC Vox 3` | Mono |
| 04 | Vox 4 | 4 | `REC Vox 4` | Mono |
| 05 | Bass | 5 | `REC Bass` | Mono |
| 06 | Guitar 1 | 6 | `REC Guitar 1` | Mono |
| 07 | Guitar 2 | 7 | `REC Guitar 2` | Mono |
| 08 | Utility Mic | 8 | `REC Utility Mic` | Mono |
| 09 / 10 | Drums EAD10 L / Drums EAD10 R | 9 / 10 | `REC Drums EAD10` | Stereo: 9 left, 10 right |
| 11 / 12 | Keys L / Keys R | 11 / 12 | `REC Keys` | Stereo: 11 left, 12 right |
| 13 | Spare 1 | 13 | `REC Spare 1` | Mono |
| 14 | Spare 2 | 14 | `REC Spare 2` | Mono |
| 15 | Spare 3 | 15 | `REC Spare 3` | Mono |
| 16 | Spare 4 | 16 | `REC Spare 4` | Mono |

Each stereo pair has one arm button and a two-channel meter. The EAD10 is a
stereo drum source, not a set of separate drum-mic inputs. All four vocal tracks
remain independent; the list does not designate a lead/backing vocal split.
Create Utility Mic and Spare 1–4 as well, with those rows in an expandable
Additional inputs group. Initial setup leaves every track disarmed; musicians
select the instruments for a take and subsequent takes reuse that selection.

The channel list does not confirm the physical source sockets (local versus
AES50 stagebox), expansion-card model or current USB patch. Use the local-input
baseline below only when the physical wiring matches. Recorded audition return
assignments are separate from these inputs and remain configurable; in particular,
do not infer vocal roles or spare-instrument destinations from channel numbers.
The existing backing return map is in [JAMROOM_DESIGN.md](JAMROOM_DESIGN.md).

## Initial X32 and REAPER setup

The following baseline assumes the instruments are plugged into the X32 Rack's
**local inputs 1–16**. If they use an AES50 stagebox, finalize the source blocks
against the actual stagebox wiring before following the mapping below.

1. Save the current mixer scene so the working rehearsal routing is documented.
   Connect the mixer USB audio card to the REAPER PC.
2. In the X32 Routing screen's Card Output tab (label may vary with firmware),
   send **Local 1–8 → Card outputs 1–8** and **Local 9–16 → Card outputs 9–16**.
   These card outputs are the audio arriving at **REAPER inputs 1–16**.
3. Keep the live mixer channels sourced from the physical inputs. Keep the
   existing computer playback returns on channels 17–32. USB sends to the
   computer and returns from the computer are separate directions; recording
   input 1 does not require changing mixer channel 1 to a Card input.
4. In REAPER's audio-device settings, select the installed card's ASIO driver
   and expose inputs 1–16 (or the larger required range). Retain the playback
   outputs already used by the jam-room project. Confirm the device and project
   sample-rate settings agree.
5. In ReaSet Recording → Setup, use **Set up recording tracks**. The completed
   default template will create `REC <instrument/mic>` tracks with named inputs
   and mono/stereo assignments. Repeating setup must not duplicate tracks.
6. Play each instrument separately and check the matching X32 and ReaSet input
   meters. Adjust the source/preamp gain to avoid clipping. For stereo sources,
   check left and right separately. Use X32 monitoring, with REAPER software
   input monitoring off by default.
7. Record a short test, Stop, then Listen. Verify the instruments and recorded
   playback destinations before recording a full rehearsal. Save the project
   and rig template once the mapping is confirmed.

Routing local inputs directly to the card captures the preamp signals, rather
than the full channel-strip mix. If processed channel recordings are wanted,
specify that before finalizing the template's direct-out/tap-point routing.
Manufacturer reference: [X32 Rack user manual, recording setup and Card Output
routing sections](https://warehousesound.com/r/behringerX32RACKmanual.pdf).

The table above is the default track specification for implementation. ReaSet
will create the REAPER tracks; it does not currently configure or rename the
X32 remotely.
