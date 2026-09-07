**Project review and chord/lyric design proposal — 7 September 2026**

Reviewed repository baseline: `b88bb35`. The findings below describe that baseline. The approved section-chart model, optional section repair, guarded bulk updates and associated fixes have since been implemented. See [delivery, migration instructions and validation](SONG_CHART_UPDATES.md) for what shipped and its limits. The original findings remain here as review evidence; not every broader recommendation has been implemented. Existing library songs were not silently regenerated.

The project has a useful foundation: REAPER owns audio playback, the PB buses give instruments stable routing, and the importer already supports source reuse, stem previews, and repair without importing everything again. Keep those investments. The main timing problem needs a better representation of the music as well as several ordinary bug fixes.

**Recommendation: preserve the chart as a structured musical document, and attach timing to it.** A chord belongs to a section and may belong to a word or a beat. Its place on the page should survive an inaccurate timestamp. An intro or solo must exist independently of lyrics.

**User clarification: immediate usability comes first.** A new import should automatically produce a usable, mostly accurate first pass. Section confirmation is an optional repair workflow, not a mandatory preparation pass. Avoid both heavy manual setup and unsupported automatic precision. This clarification governs the delivery plan below; achieving it must be demonstrated on untouched imports, not only on hand-corrected examples.

**Scope and evidence**

The review covered the browser's transport, setlists, section handling, chord/lyric rendering, repairs, Tracks and tempo/key paths; the Lua publishers and project mutation scripts; the Python importer/server; setup/update scripts; tests and documentation. `PRIOR_ATTEMPT_REFERENCE.md` was treated as historical context, not the current specification. Vendored Sortable was treated as a dependency, not audited internally.

Checks run:

- `python -m unittest discover -s tools -p 'test_*.py' -v`: all 11 tests passed.
- Both browser programs' inline JavaScript parsed successfully with Node's `vm.Script`.
- Targeted calls into the actual Python functions, with synthetic chart/audio inputs and mocked external operations, reproduced the placement, offset and repair problems below.
- Actual extracted JavaScript rendering functions were executed with a minimal DOM stub to check intro omission, expired chord display and unescaped text. This was not a full browser layout test.
- Metadata from the three local import jobs was inspected. Only Dreams had a linked chart: 34/36 chart lyric lines matched, with 85 published chords and six blank lyric markers. That demonstrates available inputs, not musical accuracy. The other two jobs had no linked chart.

No live REAPER/X32 session, acoustic timing measurements, or tablet acceptance test was performed. Findings marked “static” follow directly from code paths but still need runtime regression checks. External tools suggested later were researched, not installed or benchmarked.

**The timing failures, in priority order**

**1. High — silent-gap markers are discarded, then lyric chords are stretched into the gap. Reproduced.**

In [jamroom_import.py](../tools/jamroom_import.py), `lyric_lines_shifted` (line 1270) removes blank lyric entries. `chords_from_lyrics` (line 1343) then uses the next nonblank line as the end of the current line. Each chord's character column becomes a fraction of that interval.

A synthetic line at 10 seconds, blank marker at 12 seconds, and next line at 30 seconds produced this result:

| Authored order | Published time |
| --- | ---: |
| Lyric chord C | 10.000 s |
| Solo chord Dm | 16.667 s |
| Second lyric chord G | 20.000 s |
| Solo chord E | 23.333 s |

The lyric chord landed eight seconds into the marked gap. Sorting by estimated time then interleaved the lyric and solo sequences. The instrumental window also begins at the preceding lyric line's **start**, not the section boundary or vocal end (line 1387).

Fix direction: retain blank markers as end/gap evidence, preserve section membership, and prohibit placement across confirmed section boundaries. Character spacing is a layout hint; it is not elapsed singing time.

**2. High — Sheet view cannot render a whole instrumental passage. Reproduced.**

[ReaSet.html](../ReaSet.html), `renderChordsView` (line 9101), creates rows only by iterating lyrics. Chords outside those lyric intervals have no row. Carrying one held chord onto a subsequent lyric line does not recover an intro progression or solo.

With C/G at 0–8 seconds and the first lyric at 10 seconds, rendering at 2 seconds showed the first lyric and its Am chord; both intro chords disappeared. The first lyric row was even marked active. A separate Dm event at 20 seconds also disappeared between lyric items ending at 12 and beginning at 30.

There is another layout error: time percentage is applied to the full row width, while the importer used character position within the lyric string. Even perfect timestamps cannot recover word alignment that way, especially after wrapping or changing fonts.

Fix direction: render vocal and instrumental section rows; retain explicit chord-to-token anchors and render chord/text groups together. Use timestamps for highlighting and following, not to reconstruct typography.

**3. High — automatic vocal correlation has the wrong correction sign. Reproduced.**

[jamroom_import.py](../tools/jamroom_import.py), `stage_lyrics_align`, lines 1966–1971, calculates a lag whose sign is opposite to the shift subsequently added to lyric timestamps.

Synthetic vocal activity starting two seconds after its corresponding lyric activity produced `offset = -2.0` and `shift = -2.0`. The required correction was `+2.0`. The actual function was exercised with `_activity` supplying deterministic arrays and `_vocal_onset` returning `None`.

The vocal-onset override can mask this when a usable onset exists. It also raises `drop` to at least 0.10 when opinions disagree, making the fallback eligible for automatic application without independently establishing its reliability.

Fix direction: define the sign convention once, test positive and negative offsets plus no shift, and report disagreement as uncertainty. Vocal energy does not establish which word is being sung.

**4. High — changing the import review offset moves lyrics but leaves their chart chords behind. Reproduced.**

[jamroom_importer_server.py](../tools/jamroom_importer_server.py), `run_apply` (line 903), updates `offset_override` after chart generation without rebuilding dependent chords. [jamroom_import.py](../tools/jamroom_import.py), `write_reaper_job` (line 2080), emits the chord times unchanged but adds the new offset to lyric times.

An actual generated Lua job, using mocked application to REAPER, contained a chord at 10 seconds and its lyric at 12 seconds after a +2-second review adjustment.

Similarly, `/api/lyrics_pick` changes the review job's lyric source without regenerating an already selected chart. Fix dependency invalidation at the job level, so every UI route uses the same rules. Preserve the distinction between a recording-wide shift and a vocal-only correction: instrumental timing should not automatically move with every lyric edit.

**5. High — chart replacement leaves corrections tied to the old timestamps. Reproduced call path.**

[jamroom_importer_server.py](../tools/jamroom_importer_server.py), `rechord_song` (line 688), installs new chords without calling `_clear_repairs`; a mocked replacement confirmed zero calls. [jamroom_rechord.lua](../tools/jamroom_rechord.lua) does not clear them either. The lyric replacement path does clear repairs afterwards.

Consequently, a timing curve for the previous chart is applied to the replacement, while the old reviewed flag may still be present. Changing the chart can immediately make the new result wrong again.

Fix direction: associate repairs and review status with a source revision. Replace items and invalidate incompatible repairs in the same REAPER undo transaction. The current separate HTTP clear after lyric replacement is also vulnerable to interruption and undo inconsistency.

**6. High — section structure, repetitions and uncertain matches become unsupported exact timing. Parser/alignment behavior reproduced.**

[jamroom_import.py](../tools/jamroom_import.py), `ug_chart_blocks` (line 1043), keeps chords, columns and an optional next lyric line, but drops section labels and does not expand repeat instructions. A synthetic `[Intro] C G x4` followed by `[Solo]` produced two unlabeled chord-only blocks with no repeat count. Unmatched vocal blocks are subsequently grouped with instrumental blocks.

`_align` (line 1151) deliberately permits unrelated chord pairs. `_align(['C','F'], ['F#','B'])` pairs both positions. Callers count such pairs as anchors; coverage therefore measures assignments, not correct harmonic matches. In the lyric-led path, instrumental matching also happens before applying the chosen key offset, unlike the detector-led fallback.

`_finish_chords` (line 1283) removes adjacent identical symbols and changes less than 0.30 seconds apart, then extends each remaining event to the next. The sparse-chart check rejects fewer than 12 resulting events or an average spacing above 15 seconds. These rules can erase legitimate repetitions, fast changes and sustained harmony; they cannot distinguish those from a bad import.

Fix direction: retain repeats, section occurrences and no-chord/rest information; distinguish mismatched assignments from evidence; assess quality locally. Do not use chord count as a proxy for musical validity. A human chart is a candidate arrangement, not automatically the exact recording.

**7. Medium — the lyric repair route recreates gaps differently from initial import. Reproduced.**

[jamroom_importer_server.py](../tools/jamroom_importer_server.py), `relyric_song` (line 797), uses the filtered nonblank lines and has no initial import's 15-second cap. The same 10-second line ending at a blank marker at 12 was rebuilt as a 10–30-second item.

It also calls `build_chart_chords` without preserving an explicit key override; changing lyrics can therefore reintroduce an unwanted automatic transposition. A shared source-to-item conversion should govern import, replacement and regeneration, with human overrides stored distinctly from estimates.

**8. Medium — precise views can display expired or stale chords. Reproduced.**

[ReaSet.html](../ReaSet.html), line 9055, uses `clIndexAtOrBefore` without checking the chord's end and forces negative results to index zero. At 15 seconds, an Am ending at 12 remained the big current chord. The renderer also used cached data with `clAlive()` false; its liveness check only contributes to the empty-data message.

The chunk reader at line 8962 has generation checks, which are useful, but no deadline/retry for a missing chunk from an otherwise unchanged generation. `ReaSet_ChordsLyrics.lua` silently retains previous output if `build_json` fails inside `pcall` (line 417), while its heartbeat can continue.

Fix direction: separate current, held, upcoming, unknown and disconnected states; verify song identity and freshness before following. Add bounded chunk retries, a session identifier, payload validation and a published build-error state. Keeping an explicitly labeled static chart available offline is useful; presenting stale highlighting as live is not.

**Why another alignment heuristic alone will disappoint**

The current pipeline combines three potentially different arrangements: downloaded audio, an LRCLIB lyric record and a third-party chart. It flattens chart structure, estimates times from line starts, then tries to reconstruct a chart from those estimates in the browser. Information is lost twice.

Timing checkpoints can fix a shift or drift. A monotonic time correction cannot add a missing repeat, restore a discarded instrumental section, or reorder events that were assigned to the wrong passage. Beat snapping cannot resolve those structural errors either. The code's comments mention historical accuracy percentages, but this checkout does not contain a labeled evaluation corpus that lets us reproduce those figures.

**Proposed model and player experience**

Keep a small, versioned song document alongside the imported media. Publish the performance portion through the existing Lua bridge. The importer may prepare it, but the optional importer server should not be needed to perform.

| Information | What to preserve |
| --- | --- |
| Identity | Stable song ID, recording identity, chart revision and arrangement revision |
| Arrangement | Explicit ordered occurrences: Intro, Verse 1, Chorus 1, Solo, Chorus 2, Outro |
| Chart content | Chord symbol, word/token anchor or bar/beat anchor, repeats, held chords, rests and performance cues |
| Timing | Song-relative seconds, optional beat positions, section boundaries and event durations; unresolved values allowed |
| Evidence | Human placement, word alignment, harmonic evidence or interpolation; retain alternatives/disagreement |
| Review | Section/event review status tied to the reviewed revision, plus reversible edits |

Repeated sections can reference shared chart content while retaining separate occurrence IDs and timing. A shortened final chorus is an occurrence-specific variation, not a reason to distort the entire song. Detecting silence is evidence of a gap, not permission to declare every vocal gap a solo.

ChordPro is worth supporting for editable import/export: it represents chords with lyrics and provides labeled section environments. Timing should be a companion layer; ChordPro by itself does not solve alignment. Start with a declared subset and report unsupported constructs. [ChordPro chord/lyric format](https://www.chordpro.org/chordpro/chords-over-lyrics/), [section environments](https://www.chordpro.org/chordpro/directives-env/).

An instrumental passage can look like this (illustrative music):

```text
INTRO · 8 bars
| Am | F | C | G |  ×2

VERSE 1
Am                 F
An example lyric phrase

LEAD BREAK · 8 bars
| Am | F | C | G |  ×2
Next: Chorus
```

Show a bar counter only when the meter and bar boundaries are known. Otherwise show the progression and section label without a fabricated counter. Preserve an explicit distinction between “N.C.”, silence, a sustained chord and “chord unknown.” Riff cues can be more useful than a stream of guessed chords.

During vocal sections, render each chord above its associated text token. For charts whose wording differs from the lyric record, store and review the mapping; do not assume equal character offsets in two different strings. Layout should remain stable across font changes and wrapping.

**Default workflow: import, open the chart, play**

After source selection, automatically preserve chart headings, repeats and chord/text relationships; match available lyric passages; and propose section occurrences and boundaries from the available evidence. Use existing REAPER sections where present. Missing labels can remain neutral passage names. A chart need not print every verse or chorus, but reusing earlier material needs an explicit repeat instruction or sufficient supporting evidence; unknown harmony remains unresolved.

Choose display precision locally, independently of whether a human has reviewed the song:

| Available evidence | Automatic first-pass behavior |
| --- | --- |
| Reliable chord/text relationship and well-supported event timing | Render the relationship and follow the timed events. Automatic support is not labeled human-reviewed. |
| Passage content and approximate location are supported, individual chord times are weak | Show the full passage/progression, with surrounding context; avoid exact chord highlighting. |
| Instrumental content is known, internal durations are uncertain | Show a labeled progression or pattern without invented word anchors or bar counters. |
| Section identity or content is ambiguous | Keep the source chart readable, expose a small local uncertainty indicator and allow manual navigation; do not automatically attach unknown chords to nearby lyrics. |

These behaviors must be useful defaults rather than a maze of confidence settings. Retain working passages when one passage is uncertain. Do not block playback on a review checklist, require listening through every song, or hide uncertainty behind a misleading percentage. A poor or incomplete source can still require a better chart; fallback display cannot manufacture missing harmonic content.

**Optional repair workflow: fix the passage that interrupted rehearsal**

Let the operator play the relevant passage and tap “Verse starts”, “Solo starts”, or “Chorus starts”, with replay and small timing adjustments. Offer local operations such as “starts here”, “uses this earlier progression”, “repeats twice” and “different section”. Within an instrumental section, allow editing its pattern and repeat/bar count. Recompute only affected estimates and preserve unrelated human edits. Chord-by-chord tapping is not the normal repair path.

For regular passages, a start point, end point and known bar count can establish useful timing. Variable tempo, pickups, odd meter and partial bars need additional anchors only if more precise following is wanted. Do not force those songs into a constant-BPM formula or modify audio item positions to accommodate a chart. Keep automatic, human-reviewed and previous revisions separately so an experiment can be rolled back without making human review a requirement for use.

The separate stems are a useful asset: vocals can inform word timing, percussion can suggest beats, and bass/guitar/keys can inform harmony. Combine evidence inside a confirmed section; retain uncertainty where it disagrees. Neither a vocal-onset detector nor every change in an audio chord classifier establishes a true chord change.

WhisperX supplies forced alignment and word timestamps and is a candidate for an offline preparation experiment. Its documented focus is speech; singing accuracy must be established on this library, especially sustained vowels, backing vocals and ad-libs. It is not a prerequisite for fixing intros or chart layout. [WhisperX project](https://github.com/m-bain/whisperX).

Beat tracking can supply candidates, including with a supplied tempo, but it must not silently choose the downbeat or overwrite reviewed timing. Test phase, half/double tempo and syncopated changes. [librosa beat tracker](https://librosa.org/doc/main/api/generated/librosa.beat.beat_track.html).

**Broader reliability findings**

| Priority | Finding and evidence | Recommended direction |
| --- | --- | --- |
| High | Tempo/key bookkeeping is not scoped to a project. `ReaSet_TempoKey.lua` keeps `applied` globally, visits current-project items, and replaces the map at line 280; its loop does not detect project changes. Switching tabs can strand offsets in the old project and subsequently compound them. Recovery only runs at script startup. Static. | Track ownership by project and take identity; restore the original project's changes before switching, or maintain explicit per-project state. Test switching while transposed and after saving/restarting. |
| High | Every browser can send its own saved tempo/key on song entry (`tkTick`, `ReaSet.html` line 5162). Multiple tablets can overwrite one another, including with default 100%/0 settings. `tkLoadSettings` is called at initial script evaluation but not when project storage becomes known. Static. | Keep shared musical settings in the project; make display-only followers the default and choose an explicit transport/settings controller. Reload project-scoped preferences consistently. |
| High | `jamroom_rechord.lua` validates name/start, but not the current region end (line 72), before deleting through the request's old end. After shortening a region and adding a neighbor, a stale replacement can remove neighboring text items. It also clamps an item's end after its positive-duration check, potentially creating an invalid duration for an event starting past the region. Static. | Validate project, song identity, revision and both bounds immediately before mutation. Clamp and validate every new item before deleting old items. |
| High | `jamroom_delete_song.lua` deletes every media item beginning in the region on every track (line 82), not only importer-owned stems/text. User recordings and unrelated material in that interval are included. Deleting audio files cannot be undone by REAPER. Static. | Tag/import-manifest ownership, preview deletion scope, and check remaining references before removing shared source files. |
| Medium | Rechord/relyric save `job.json` before REAPER acknowledges application. `lyrics_pick` and `ug_use` bypass the `BUSY` lock despite a threaded server and shared job/tmp files. Static. | Use one mutation coordinator, immutable candidate revisions, operation-specific request/receipt IDs, and pending/applied states. Retain candidates on failure without calling them installed. |
| Medium | Blank project-ID replies do not clear an existing `g_stableId` (`ReaSet.html` line 4342). Song settings variously use display names, raw names, region IDs and start times. Delete does not remove timing repairs keyed by the deleted region ID. Static. | Use one project/song identity scheme and explicit migration. Invalidate old state on project switches; prevent name changes and reused region IDs from adopting unrelated repairs. |
| Medium | Chord/Sheet/precise-lyric rendering inserts unescaped item text into `innerHTML` (lines 9080, 9157, 9238). A harmless `<b>RAW NOTE</b>` was emitted as markup in the renderer check. | Render ordinary text using `textContent` or the existing escaping helper; define a narrow supported markup format if needed. |
| Medium | The importer binds all network interfaces (server line 1333), exposes mutations without application authentication, and its audio containment check uses string-prefix matching (line 994). A similarly prefixed sibling folder can pass that check. Static; no network exploit attempted. | Add deliberate device pairing/access controls for maintenance, origin checks, bounded request bodies and path-component containment. Keep performance controls separate from destructive maintenance capabilities. |
| Medium | `JamRoom Update.bat` line 49 omits both `ReaSet_ChordsLyrics.lua` and `ReaSet_TempoKey.lua` from restart detection. An update to only these scripts is reported as requiring no restart. The deploy script reports success without checking copies. Static. | Derive restart requirements from a component manifest; check deployment results and show the versions actually running. |
| Medium | `JamRoom Importer.bat` line 8 force-kills whichever process owns port 8765, even if it is busy or unrelated. Static. | Verify process ownership and request a graceful shutdown; distinguish idle, preparing and applying work. |

Routing should retain the fixed PB convention. However, descent under a PB folder alone does not validate every actual send or master-send setting: the discovery code does not inspect those. Add an on-demand routing validator that checks the complete intended path, bypass sends and hardware destinations. Report discrepancies; do not silently rewrite an operator's routing.

**Inefficiencies and maintainability**

- **Duplicate rendering and polling.** `ReaSet.html` requests legacy lyrics every 10 ms while also using the full timeline. It rebuilds both chord and lyric HTML on transport replies at roughly 30 Hz, including hidden views; lyric rendering can run again at the end of the reply handler. Cache the parsed document, update content when the visible section changes, and update only highlights/progress with the clock. Keep a controlled legacy fallback during migration. Actual HTTP throughput depends on REAPER's scheduler and was not measured.
- **Repeated discovery.** Both ChordsLyrics and TempoKey enumerate and compare all regions inside each deferred tick. Cache region structure until project changes and search the cached intervals for the current position. JamRoom also rescans on general project changes, so a mute or unrelated edit can cause structural work. Profile a representative large project before choosing further optimization.
- **Audio analysis allocations.** `_activity` in `jamroom_import.py` line 1818 builds a dense overlapping-window index matrix. At five minutes/22.05 kHz, that index alone is approximately 202 MiB, before sampled windows and intermediate arrays. Use streaming/block RMS or cumulative sums; retain the same mathematical result and cache the envelope for subsequent checks.
- **Competing playback ownership.** NativeLoop and browser code both count loop crossings, while browser playback UI also sends stop/jump commands. Consolidate boundary actions under one REAPER-side controller over time. The browser should request actions and display confirmed loop state; test closure/disconnection and two open clients explicitly.
- **Limited regression protection.** Four timing tests validate a Python reference interpolator, not the Lua implementation. Several others check that source strings exist. Preserve those where useful, but add tests of actual placement, parsing, render selection, failed mutations and project switching. There is no checked-in verification script matching the timing-test docstring's claim.
- **Documentation drift.** `CLAUDE.md` still describes no backend/cloud dependencies, while the importer has a Python HTTP server and uses external sources. Startup launches six scripts although comments and README describe four. Update the architecture facts so future agents distinguish offline performance from online preparation. Preserve dated decisions and label hypotheses separately from verified behavior.

The 9,435-line browser file, 2,266-line importer and 1,362-line server are workable deployment artifacts but difficult units of reasoning. First extract pure functions and explicit subsystem boundaries without changing behavior. A framework migration is not needed to fix this. Later, discuss splitting source files or generating the existing single-file deployment only if it materially improves maintenance.

**Feature, workflow and UI suggestions, ordered by value**

| Value | Improvement | Benefit |
| --- | --- | --- |
| First | Section-aware Sheet view and tap-to-mark section editor | Solves the specific intro/solo workflow and gives corrections a musical scope. |
| First | One “Review this song” workspace | Brings recording choice, chart structure, lyrics, timing, key and playback preview together; reports why a passage needs attention. |
| First | Automatic and human-reviewed revisions with rollback | Makes experimentation reversible while keeping the automatic first pass immediately usable. |
| First | Bulk “Update lyrics & chords” with song exclusions | Brings existing REAPER songs onto improved encoding/timing without repeated individual re-imports. Persistent “Keep this version” protects known-good songs. |
| First | Controller/follower device roles | A singer's tablet can follow without imposing its setlist or tempo defaults on the band. Capo, font and lookahead remain personal. |
| First | Complete backup/restore | Existing setlist export exports `setlists` only. Include a versioned bundle/manifest for charts, repairs, overrides and references, with audio as a separate optional component. Validate on restore. |
| Next | Section loop, count-in and practice tempo ramp | Extends existing rehearsal controls; derive counts from validated beats and execute through the REAPER controller. |
| Next | “Next section” and “vocal entry” cues | Instrumental passages become useful preparation time instead of a frozen lyric. Only show precise countdowns when timing is reviewed. |
| Next | Section review status and disagreement markers | Direct listening effort to a suspect solo or repeated chorus instead of replaying the whole song after every change. |
| Next | Performance lock and resume-follow button | Avoid accidental maintenance/transport changes and stop auto-scroll fighting someone reading ahead. |
| Next | Personal chart preferences | Nashville/scale-degree view, enharmonic spelling, capo shapes, accessible contrast and existing foot-controller navigation, all driven by one chart model. |
| Later | Practice notes/bookmarks by section | Capture “enter after drums” or “repeat bridge twice” alongside existing section notes and loop controls. |
| Later | Portable local song packages | Reuse reviewed arrangements across REAPER projects while binding each package to the correct recording/version. |

**Required upgrade workflow for existing song libraries**

User requirement: every improvement must be usable on songs already loaded in REAPER. A new importer that only helps future songs is incomplete. Ship the relevant upgrade path alongside changes to generated song data, with one batch action and optional per-song exclusions. This is an explicit maintenance action, never an automatic rewrite when opening a project or installing a release.

Player-facing entry: **Update lyrics & chords**. Default scope is the current displayed song list/setlist, with an explicit alternative for all songs in the current REAPER project. ReaSet supplies the selected song identities because its active setlist is browser-local; the importer must not assume the project song list equals the active setlist. Deduplicate songs within the batch and reconcile legacy songs against current project regions before enabling a write.

The list shows a checkbox, song name, update status and optional persistent **Keep this version** setting. Select eligible outdated songs by default; users can deselect any song for this run. Protected songs stay excluded in future batches until deliberately unlocked. Offer Select eligible / Deselect all. Already-current songs are skipped on a normal update; an explicit rebuild remains available for recovery. Do not equate the existing reviewed flag with reliable protection, because earlier code sets it after individual repairs.

Distinguish the work needed:

| Change | Upgrade behavior |
| --- | --- |
| Display-only rendering fix | Available after the relevant application/bridge update; no song-item rewrite. |
| Lossless representation/schema change | Migrate existing content and timings while preserving edits. |
| Improved parsing, structure or timing generation | Rebuild affected derived data from the recording's saved inputs and selected chart/lyric sources. |
| Missing or ambiguous source/identity | Leave the existing song available and report the missing requirement; continue other eligible songs. |

Track data schema, generator versions by component, source revisions and installed revision separately. An app version alone cannot identify whether a song needs new encoding. Existing unversioned jobs are explicitly legacy/unknown, not presumed current. Source dependency records determine which stages need rebuilding, so a lyric-layout change does not rerun audio separation. Normal upgrades reuse cached lyrics, chord evidence, audio/stems and the chosen chart source. Some older jobs retain only a chart URL rather than a parsed source: they may require a fetch, and any changed source must be recorded as such. No automatic new recording selection, paid processing, stem separation or full audio re-import as a fallback.

Batch operation:

1. Read selected songs from the target project and produce candidate revisions with the shared importer pipeline. Show progress; require no per-song timing review. A structural validation failure leaves that song unchanged, but uncertainty that the display can handle should not unnecessarily block an otherwise useful update.
2. Capture durable snapshots of the affected REAPER text items, relevant section metadata, repairs/review flags and installed job revisions before applying changes. Snapshot actual REAPER state, not just the possibly older job file. Make rollback available per song and for the batch after restart; REAPER's transient undo history alone is insufficient.
3. Apply serially while transport is stopped, verifying project/song identity, both region bounds and the expected prior revision immediately before each replacement. An ordinary song failure does not stop the remaining batch; a changed target project or other unsafe global condition pauses application. Preparation can continue independently of playback, but application must not silently stop a rehearsal.
4. Replace only the affected lyrics/chords and generated section metadata, with repairs handled in the same transaction. Keep song regions/IDs/positions, stems, routing, mutes and setlists intact. Record the installed revision only after a matching REAPER receipt. Commands carry operation IDs so retrying after a lost receipt does not apply twice.
5. Finish with a concise receipt such as “18 updated · 4 protected · 2 need attention”, including reasons and Retry / Restore previous version actions. Persist progress so an interrupted batch resumes or reconciles completed operations rather than starting over.

Preserve manual choices such as chart selection, explicit key choices, section labels and compatible corrections. Reapply event-linked edits only when their references still resolve against the rebuilt content. Never blindly reuse old source-time correction curves on new timestamps. If edits cannot be safely transferred, retain the existing song and flag the conflict; offer a deliberate rebuild that replaces those edits from the batch list. Older direct REAPER edits may have no provenance, so migration must record uncertainty rather than claim it can identify every authored change. Explicit “Keep this version” remains the dependable user control for known-good legacy songs.

Acceptance cases: mixed old/current/protected songs; a batch scoped to one setlist; preserved region IDs and audio; missing cached sources; incompatible manual repairs; changed region bounds; project switching; failure halfway through; restart/resume; duplicate requests; per-song and whole-batch rollback; and repeating an update without unnecessary changes. A rollback must refuse to silently overwrite newer edits made after that batch. Show estimated work from available inputs, but do not promise an instantaneous batch: analysis may take time even though initiating it requires little operator effort.

**Suggested delivery order and acceptance evidence**

1. **Stabilize existing behavior and establish upgrade bookkeeping.** Fix correlation direction, preserve gaps consistently, invalidate dependent chart output on lyric edits, clear incompatible repairs transactionally, preserve explicit key choices, and fix restart detection. Add deterministic regressions before each correction. Introduce versioned source/installed records and snapshots before testing replacements; do not silently bulk regenerate the library during development.
2. **Prove the document/rendering model on one song.** Introduce an optional structured chart while retaining existing item timelines as a compatibility path. Hand-author one intro, vocal section and lead break, including a repeat and a rest. Prove readable Sheet rendering without relying on precise chord highlighting.
3. **Prove automatic first-pass usability, then add local repair.** Automatically assemble candidate sections and repetitions, align supported passages, and apply the display fallbacks above. Test without hand-editing each song. Add section repair as an optional correction path; retain every edit and source revision. Additional beat/harmonic/word analysis must earn its complexity through improved first-pass results or reduced correction effort.
4. **Unify runtime state.** Make Lyrics, Chords, Canvas and Live consume the same selected revision and correction layer, whether automatic or human-reviewed. Enforce project identity, freshness, controller ownership and recovery. Address the high-risk tempo/key and mutation findings before extending those features.
5. **Evaluate before wider rollout.** Use a small fixed set of manually labeled songs with intros, long solos, repeated choruses, sustained chords, tempo variation, pickups and a mismatched chart. The three cached jobs are useful starting material but are not a sufficient labeled benchmark.
6. **Deliver existing-library upgrades with the data changes.** Expose the tested bulk update, song exclusions/protection, resume and rollback paths before releasing new encoding/timing as ready for routine use. Use the same generation code for fresh imports and upgrades so legacy songs do not become a separate, diverging implementation.

Measure section identity, event order, missing/extra chords, and timing error separately. Report timing within 100/250/500 ms and median/95th-percentile error, plus human correction effort. Separately record the proportion of songs usable without edits, misleading automatic placements, manual actions/time per repaired song, and time until a chart becomes available. Report untouched automatic output separately from repaired results, and report how much material received precise timing so abstaining everywhere cannot masquerade as accuracy. Initial numerical targets require a baseline; do not promise a success rate or processing time before measuring. A high line-match percentage or proximity to a detector's changes is not independent ground truth.

Required regression cases include the synthetic 10/12/30-second gap above; positive/negative vocal offsets; changes to lyrics after chart selection; replacement after saved repairs; intro/solo-only rendering; N.C./rests; seeking and looping; multiple tablets; missing/stale chunks; failed apply followed by retry; project switching while transposed; and moved or shortened regions before mutation.

Success means most new songs are useful immediately after automatic preparation, a musician can still read a passage whose detailed timing is uncertain, and occasional local repairs leave working passages intact. A mandatory lengthy section-review pass would fail the product requirement even if the final corrected chart were accurate. Precise highlighting is an additional capability built on that foundation.
