# Paramore - Misery Business: default-import visual review

Testing workstation only. Imported the already-split Fadr asset
6a8ad132bc73956386d14750 through the visible importer buttons. Existing primary
and secondary splits were reused, with no new separation charge. Default stem
assignments produced six groups. Selected the first Ultimate Guitar result,
version 2: https://tabs.ultimate-guitar.com/tab/paramore/misery-business-chords-531366
Timed lyrics: LRCLIB 3828663. Automatic key adjustment: +1 semitone.
The song is region 6 at 895 seconds in JamRoomTest.RPP, saved for inspection.

## Verdict: partial success, not an unattended musical-quality pass

Source words and chord offsets are preserved for every row. The lyric matcher
reports 50/50 rows, but that does not establish correct structure or playback
cues. All 155 source chord anchors render once at each tested screen size.

- 1440x1000: 12 pages; 768x1024: 12 pages.
- 390x844: 30 pages; 1024x768: 21 pages.
- No horizontal or vertical clipping across all 75 pages checked in real ReaSet.
- Phone pagination is much more fragmented and needs separate usability review.
- Actual images were inspected for verses, choruses, instrumental patterns and outro.
- No listening-based verification of automatic timing or key was performed.

## Defects exposed

The prior control cleanup accidentally removed the shared Fadr picker and import
entry points along with obsolete lyric-repair functions. Restored the original
entry points and added a browser test that uses the visible library, selection
and import buttons.

Transposition widened tightly printed repeated chord names, making D# and C#
sequences run together. The renderer now adds space only in instrumental space
or after the lyric ends; anchors over words and the stored source remain intact.
A browser regression test covers this. Fresh screenshots confirm the correction.

Still unresolved in the default result:

1. The source's second [Instrumental] heading is followed by the second chorus
   without a new [Chorus] heading. The importer consequently labels sung chorus
   rows Instrumental. This needs a split and rename in Edit sections.
2. The first Instrumental runs from 36.83 to 37.03 seconds: a 0.2-second estimated
   page is not a useful performance cue. It needs playback review and correction.

The default source sections and cue guesses were left unedited to preserve the
actual test result. Successful matching and unclipped pages are insufficient
acceptance criteria for a rehearsal-ready import.

Evidence: imports/.visual/paramore-import/, including review.json, source-chart.txt,
chorus.png, mislabelled-chorus.png, outro.png and saved.txt.
