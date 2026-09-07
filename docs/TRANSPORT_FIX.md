# Stop/Play and post-import transport fix

The browser can send real REAPER transport commands, so a delayed browser Stop
can interrupt Play pressed in REAPER itself even with only one ReaSet tab open.
The investigation reproduced seven faulty sequences before fixing them:

- MIDI initialization's delayed Stop survived an ordinary Play-button click.
- Stop's delayed return-to-start survived playing a different song.
- A library redraw evaluated auto-stop using the previous transport snapshot.
- An old end-of-song response could stop newly requested playback.
- A delayed next-song start survived a manual Stop.
- A reply containing TRANSPORT before updated REGION data used old boundaries.
- Play immediately after Stop sent Pause while awaiting the stopped reply.

The page now gives scheduled transport actions an operation identity. New Play,
Pause, Stop, Cue, project changes and region changes cancel obsolete actions.
Fresh transport replies drive automation; rendering alone does not. The request
start timestamp supplied by REAPER's `main.js` rejects old snapshots even if
they arrive more than 500 ms later. Playback decisions wait until the complete
reply has been read, including region updates.

Stop and return-to-start are sent as one ordered request. Rapid Play/Pause
decisions account for an outstanding command while displayed state remains
REAPER-confirmed. Held Enter/Space keys do not repeatedly fire transport actions.
An observed external playback start cancels a pending automatic cue or delay.

Automatic end-of-song cues no longer briefly Play/Stop to initialize MIDI.
The MIDI Init option still supports that pulse for explicit Cue, and a new
browser Play or Stop cancels its pending Stop.

Validation: **59 automated tests passed**, including 13 new browser transport
regressions and checks that auto-stop still fires once and chaining still works.
An additional browser check used the actual installed REAPER `main.js` request
queue against an intercepted HTTP transport fixture. Auto-stop, simulated
external Play, and rapid Stop/Play passed with no browser errors. The real song
library was not modified, and playback was not started in the loaded project.
These reproductions identify real faults; they cannot establish that every
possible cause of the reported playback failure has been eliminated.

Deployment requires only refreshing ReaSet. The sidebar should show
**v1.9 - transport fix**. On another installation, run JamRoom Update first.
No song re-import, database migration, or REAPER restart is needed for this fix.
