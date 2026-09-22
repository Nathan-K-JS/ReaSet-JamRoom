# Initial recording setup

Recording workspaces, per-part levels and solo overdubs are available in v3.17.
See [current workflows and verification](WORKSPACE_LAYOUTS.md), and
[audio reliability and recording parts](RECORDING_PARTS.md).

The recording controller automatically creates and saves the track template below
once per saved Jam Room setlist. Run the updated `Requirements/ReaSet_Startup.lua`
in REAPER (normally your startup action), open the setlist, and stop playback.
There is no separate track-creation step. REAPER 7 with SWS is required.

Automatic setup recognizes the existing `PB DRUMS` and `PB CLICK` buses, waits
until the project is saved and recording/review is idle, and leaves other projects
alone. If you save a new project after starting REAPER, setup picks it up then.
It creates missing template tracks without changing existing recording routing or
levels. Subsequent starts do not recreate tracks you intentionally removed;
Record > Settings > Create missing tracks remains available for that.

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
Remember those selections across songs and visits; show confirmed REAPER arm
state when entering the recording screen. The one-time setup stays separate from
the everyday Record / Stop / Listen / retry controls.

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
5. Open the saved Jam Room setlist with the updated startup controller running,
   and stop playback. The controller creates and saves the **Recording** folder
   and all 14 named tracks automatically, with mono/stereo inputs assigned and
   software monitoring off. Open Record and select the instruments to check.
   If using a custom bus layout, **Set up recording tracks** is still available
   manually; repeating it does not duplicate owned tracks.
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

ReaSet creates the REAPER tracks; it does not configure or rename the X32 remotely.

Recording audition defaults to the existing playback-return destinations: drums
outputs 1/2, bass 4, guitars 5/6 and 7/8, keys 9/10, all four vocals 13, and utility/
spares 15. These are **REAPER hardware output numbers**, not X32 live input
channels. Setup lets you change each first input and first output; stereo tracks
use the next channel as well. Vocal tracks remain independent even though their
default audition destination is shared.

Record a short test and confirm the intended IEM/room levels. Hardware monitoring
stays on the X32; ReaSet disables REAPER input monitoring to avoid a delayed
duplicate live signal. Recorded playback can use any configured room/IEM return.

Takes save automatically under `<setlist.RPP>.recordings/`. Stop is enough to keep
a take. Export creates a verified independent project; Delete and Discard remain
recoverable and retain raw audio. See [Playback and recording](PLAYBACK_AND_RECORDING.md)
for everyday operation, recovery and current limits.

## After stopping a take (v3.17)

Stop saves the take. The review workspace shows recorded parts and their saved
levels, with **Recorded parts / Backing** tabs for song recordings. **Listen**,
**Add part**, **New take** and **Export recording** stay at the bottom while the
mix scrolls. Use **Takes** to compare versions and **Sessions** for older work.

- **New take** prepares an independent alternative. Change inputs and count-in,
  then press **Record take**. Earlier recorded parts stay silent.
- **Redo take / Redo latest** prepares a replacement for the latest pass. The old
  pass is discarded only after recording starts. **Cancel** returns to review.
- **Discard take / Discard latest** discards that pass without starting another.
  A discarded addition returns to its parent arrangement. Restore is under
  **Sessions > Discarded takes > Restore take**.
- **Export recording** opens a focused confirmation. **Create MP3** opens the
  selected export's progress, download and QR links; **Back to recording** returns
  to ReaSet. **Exports** reopens existing exports. Keep the importer running for
  processing and room-Wi-Fi downloads; queued exports resume when it starts again.
- **Done** finishes review and releases the song for normal playback.

**Sessions > Export multitrack project** exports kept takes with
original stems into an independent REAPER project. Setlist recordings are cleared
only after verification. An MP3 export does not clear the multitracks.

## Building a recording yourself

1. Open Record and wait for inputs to connect. Choose Song or Free jam, select
   instruments, choose click/count-in, then Record.
2. Stop and Listen. Each recorded part has a Hear switch and level slider; its
   **More** menu contains Rename and Reset level. Levels save on slider release.
3. Choose **Add part**. Select this pass's inputs. Reusing Vox 1 or Guitar 1 creates
   a separate performance; the earlier recording remains available to hear.
4. Desktop shows inputs beside accompaniment. Phone has **Inputs / Accompaniment**
   tabs. Click/count-in and free-jam **Stop at end** sit above these panes.
5. Press **Record part**. Stop opens the combined arrangement. **Redo latest**
   prepares that addition again; **Discard latest** returns to the prior combination.
6. Balance the parts and choose **Export recording** for the MP3. For another
   version, choose an earlier take using **Takes**, then Add part.

Overdubs start at the beginning; punch-ins, comping and effects remain REAPER work.
Live monitoring comes from the X32, not REAPER input monitoring. **Settings**
contains track creation, routing and device controls; routine sessions reuse them.

The count-in now runs on the same REAPER timeline as capture. REAPER's native
record indicator lights before the first count-in click; that is intentional.
The lead-in is hidden from normal review and export while raw audio remains on disk.
Recording uses temporary items beyond the setlist, then returns aligned recordings
and the cursor to the session's song location. Original songs are not moved.

If inputs cannot connect, check the X32 USB cable, REAPER audio driver and enabled
input range, then choose **Reconnect inputs**. You no longer need to play a song
first. Device availability and silence are separate: a quiet input can still be Ready.
