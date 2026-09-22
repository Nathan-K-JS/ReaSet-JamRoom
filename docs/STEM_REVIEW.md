# Stem review reliability — v3.19

Quiet or brief Fadr stems now default to **Extras**. Unmapped instrument names
also go to Extras. Their audio remains in the song, including spill and short
bursts that contribute to the complete backing track. Only verified digital
silence is automatically excluded. You can still assign a genuine brief solo
to its instrument, or deliberately select Don't import.

The activity label describes how much audio was measured; it does not claim
to recognize an instrument or distinguish spill from a solo. Silence checks
examine every channel, so opposite-polarity stereo cannot cancel into a false
empty result. Analysis failures retain the audio and show an explanation.

## Accurate audition

Stem previews and the separate vocal lyric-check player use the validated PCM
WAV already prepared for REAPER. Some original Fadr MP3s reported incorrect
durations and seeking positions, even though the decoded waveform was correct.
The waveform, player and cursor now share the same decoded asset and duration.

Click or drag the waveform to audition a position. Arrow keys move one second;
Shift + arrow moves ten seconds, and Home/End move to the boundaries. Loading,
seeking and errors appear beside the player. Opening another preview pauses the
previous player. This private audition change does not add a WAV sharing option.

## Existing import reviews

Opening an unfinished review refreshes its audio metadata once. Old nonempty
Don't import choices are recovered into Extras, with a message showing the
number recovered. The previous format could not distinguish automatic skips
from deliberate ones, so this migration prioritizes keeping audio.

Other routing, names, authored charts, lyric offsets and project targets are
retained. Explicit choices made in v3.19 are recorded and survive reopening.
An Apply already submitted or awaiting recovery is not changed by migration.

Already-imported projects are unchanged. Recovering stems omitted from those
projects requires deliberately rebuilding/reimporting their stems from the
cache; updating charts, clicks or playback levels alone does not do that.

## Validation and installation

All 257 regression tests passed. Coverage includes digital silence, quiet audio, brief bursts, stereo cancellation,
truncated WAVs, stale caches, Extras summing, journal migration, explicit choices,
HTTP ranges and HEAD, browser metadata and seeking, and expanded phone layouts.
Chromium's Web Audio analyser verifies the actual frequency heard after seeking;
the Windows WebKit test runtime verifies media duration/position but does not
expose Web Audio. Physical phone/network acceptance remains a room-side check.

The cached Fly Away lead vocal now reports **222.537 seconds** in both Edge and
WebKit through the production audio handler, including old MP3 preview URLs.
Previously it reported 1153.358 and 986.149 seconds respectively. A disposable
REAPER import with five stems combined into Extras passed native and ReaSet
playback checks; the original project was restored unchanged.

Run **JamRoom Update.bat**, restart the importer, refresh the importer page and
reopen your saved review. Confirm **v3.19**. Conversion and analysis use cached
audio; no additional Fadr split is needed.
