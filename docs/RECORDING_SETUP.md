# Initial recording setup — proposed template

Recording is still being designed. This guide defines the setup to ship with
the feature; no recording tracks have been created by this documentation update.

## Input list needed

The repository records the convention **X32 channels 1–16 = live inputs** and
**17–32 = playback returns**, with a complete backing return map in
[JAMROOM_DESIGN.md](JAMROOM_DESIGN.md). It does **not** contain the instrument/mic
assignments for the live inputs. The playback map cannot supply that information.

Provide the current input list in this form, including unused inputs:

| Physical socket/source | X32 live channel | Instrument/mic | Mono or stereo partner |
| --- | --- | --- | --- |
| Local or stagebox socket number | 1 | To be supplied | To be supplied |
| … | 2–16 | To be supplied | To be supplied |

Also identify the USB expansion card if it is not X-USB. The final default will
list every source, USB input, recording track name and audition return bus. Stereo
pairs and drum mic groups will follow the supplied list, not an assumed band setup.

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

The completed template will include an exact instrument-by-instrument table and
the corresponding mixer labels. ReaSet creates REAPER tracks; it does not
currently configure or rename the X32 remotely.
