# Free-jam recording

Approved implementation: one Recording screen with Song / Free jam selection.
Choose live inputs, tempo (40-240 BPM), beats per bar (2-7), click on/off and
independent two-bar count-in before recording. Default: 100 BPM, 4 beats, click on.
No backing song is required. Only selected hardware inputs are captured.

Reuse native recording, pause/resume, keep/retry, recovery and verified export.
A free jam has no automatic song-end stop. Each new jam has its own session;
Keep/retry uses that session's fixed tempo and click choice. Done starts a new jam.
The generated click follows REAPER transport, including pause, through the
existing PB CLICK output and level. It is not included as a recorded input.
Export contains recorded takes and the chosen tempo/meter, without library stems.

Implementation: allocate space beyond current project media/regions, temporarily
silence unrelated media with durable restoration, and use a generated looping
click item with an extending end. Remove the temporary click after capture;
restore normal playback rate/mutes. Persist settings and session metadata before
capture so restart recovery uses the existing recording journal.

Validation must cover click/count-in combinations, four-mic selection, independent
band inputs, no song-end stop, pause, retries, restart, export tempo and isolation
from original library media. Test on scratch projects only.

## Using it (ReaSet v3.8)

Open **Record**, choose **Free jam**, then tick the inputs you want:

- A cappella: select Vox 1, Vox 2, Vox 3 and Vox 4 only. Set tempo, leave click
  enabled and choose whether to use the two-bar count-in.
- Band jam: select the instruments in use, including EAD10 and Keys as stereo
  pairs when wanted. Click and count-in can each be on or off.

Press **Record**. Pause/resume stays in the same take and pauses the click too.
Stop saves the take; use Listen, Keep & record another, Discard & re-record or
Done. Saved recordings and next-start housekeeping work as for song recording.
Listen plays the recorded inputs; the monitoring click is not a recorded track.
Export creates a self-contained REAPER project with the kept takes at their
original timing and the chosen tempo/meter. REAPER can provide a metronome when
editing that project. New jams use the last recorded tempo/click settings; tempo
and click choice stay fixed when making another take in the same session.

Inputs use the existing X32 setup (live sources on card inputs 1-16); no new
routing setup is required. The click follows the first PB CLICK hardware output
and its current track level at the start of a take, with output 1 as fallback.
The generated click never arms a recording input. Time signature choices are
2/4 through 7/4. Tempo is 40-240 BPM.

## Validation

167 automated tests pass, including browser setup/review checks, invalid settings,
session allocation and extending click coverage. Live scratch REAPER checks cover
four-mic capture, all click/count-in combinations, band input selection, native
pause/resume, second takes, interrupted take recovery, export tempo/meter and
verified cleanup. The test workstation has no physical X32 inputs, so the live
capture check uses native track-output recording; verify the existing input
routing/meters on the jam-room rig. The original library remains unchanged.

A live export test caught beat-based item stretching when setting the jam tempo.
Free-jam recordings now use time-based positioning, including recovered/exported
items, so changing the export tempo grid preserves recorded audio alignment.

Update with `JamRoom Update.bat`, restart REAPER and refresh ReaSet with Ctrl+F5.
Suggested song-level loudness matching remains the next agreed upgrade.
