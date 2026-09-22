# Stem review: preserve audio and make audition timing reliable

Status: implemented in v3.19. See [Stem review](STEM_REVIEW.md) for the delivered
behavior and validation. Baseline v3.18.

## Intended behavior

Keep every useful component of the Fadr separation. Brief notes, spill and quiet
parts still contribute to the reconstructed song. Default uncertain, quiet or
sparse stems to **Extras**. Automatically choose **Don't import** only for a
successfully decoded stem containing actual digital silence throughout.

The waveform, its cursor, the native audio controls and the lyric vocal player
must refer to the same audio asset and the same recording-relative clock.

## Confirmed findings

1. `stem_profile()` in `tools/jamroom_import.py` calls anything peaking below
   -35 dB "silent", and anything active for less than 4% of the song "almost
   empty". `build_review()` automatically excludes both categories. Neither
   category proves emptiness. For example, the cached acoustic stem for
   **The Darkness — I Believe in a Thing Called Love** peaks at -8.2 dB, but its
   0.2% activity classifies it as "almost empty" and makes it a skip candidate.
2. Unmapped stem types also default to SKIP in the review; mixdown separately
   ignores unmapped stems. Both paths need the same keep-audio policy.
3. `_preview_file()` deliberately substitutes the original Fadr MP3 for the
   converted `.riff.wav` used in REAPER. The originals have `.wav` filenames even
   though their contents are MP3. Some originals expose incorrect duration and
   seeking information. Waveforms are built by a full decode and therefore use a
   different time scale from the browser's MP3 player.
4. Reproduced with the existing HTTP audio handler on the test workstation:

   | Fly Away stem | Decoded WAV duration | Edge: original MP3 | WebKit: original MP3 |
   | --- | ---: | ---: | ---: |
   | Lead vocal | 222.537 seconds | 1153.358 seconds | 986.149 seconds |
   | Electric guitar | 222.537 seconds | 201.108 seconds | 190.455 seconds |

   Both browsers report 222.537 seconds for the converted vocal WAV. The cache's
   waveform profile also reports 222.54 seconds. This explains both the inflated
   vocal duration and mismatched scrubbing; being near the bottom of the list is
   not necessary to reproduce it. It does not establish that every reported case
   has the same cause, so multi-player and resumed-job cases remain in acceptance.
5. The audio range handler also mishandles suffix and unsatisfiable requests.
   MIME detection only recognizes a narrow set of MP3 headers. These are separate
   correctness gaps; repair them alongside the asset change. See
   [MDN range requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests)
   and [Range syntax](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Range).
6. Reviews and profiles are cached. Fixing generation alone would leave resumed
   reviews using old exclusions and old MP3 URLs. Existing slot overrides do not
   distinguish an old automatic exclusion from a deliberate manual choice.

## Implementation order

### 1. Establish one trustworthy audition asset and analysis record

- Prefer the existing validated PCM RIFF WAV referenced by the stem. Do not
  substitute its original MP3 sibling. Keep stereo and leading/trailing silence;
  do not trim, normalize or time-stretch audition audio.
- For older caches without a valid converted asset, prepare a sibling from the
  cached original with progress in Activity. Verify its header, frame count and
  successful decode, then publish it atomically. No new Fadr request or split.
  A truncated conversion must not be accepted merely because it begins `RIFF`.
- Derive duration from sample frames/rate. Generate waveform buckets and activity
  from this asset. Preserve all channels when measuring energy/peaks: opposite
  stereo polarity must not cancel into apparent silence during mono analysis.
- Measure digital silence from all samples/channels, separately from the activity
  heuristic. A tiny burst or quiet noise remains audio. Decode failures and
  missing files are errors, never proof that a stem is empty.
- Version analysis caches by algorithm and source identity (size, timestamp and
  format/frame metadata), invalidating old threshold-based emptiness results.
- Use one job-scoped, source-versioned URL contract for stem audition and the
  separate lead-vocal lyric player. Keep the vocal audition selected by source
  identity even if its playback routing is Extras or another custom slot.
- Compare decoded duration with the other stems/song; report a real discrepancy.
  Do not conceal it by clamping a wrong duration or stretching a waveform. Do not
  let browser metadata rewrite the import's song duration.

Reuse existing converted audio and byte-range streaming first. This costs more
network bandwidth than MP3 but avoids another conversion/cache layer. Only prepare
the requested player's metadata/audio rather than downloading every stem at once.
The recording-sharing feature remains MP3-only; this change is private audition.

### 2. Apply the keep-audio rule consistently

| Evidence / choice | Default destination |
| --- | --- |
| Existing explicit instrument assignment | Keep that assignment |
| Normal activity and a known mapping | Its mapped instrument |
| Quiet, sparse, brief or otherwise uncertain content | Extras |
| Unknown instrument type | Extras |
| Verified digital silence throughout | Don't import |
| Analysis failure | Retain mapping/Extras and flag analysis unavailable |

- Activity is a routing suggestion, not a claim that an instrument or spill has
  been recognized. Preserve the current sparse threshold initially; instrument
  assignment remains editable for a genuine solo or brief instrument passage.
- Share the decision function between review and mixdown so the actual imported
  audio matches the reviewed choices. Sum Extras without automatic normalization
  and without including both a parent stem and its split children. Fadr's
  duplicate aggregate instrumental output is not an additional isolated stem.
- Replace "nothing here" / "almost empty" with honest labels such as **Silent**,
  **Quiet audio — kept in Extras**, and **Brief parts — kept in Extras**.
- Remove historical suggestions encouraging exclusion. Keep manual routing
  available, including a deliberate Don't import override; nonempty exclusions
  stay visibly marked as containing audio. Avoid adding repeated confirmation
  dialogs to bulk review.
- Track automatic versus explicit choices from this version onward. Choose the
  destination before assigning its default label, so Extras cannot inherit an
  accidental instrument label from the old suggestion.

### 3. Refresh unfinished imports without losing review work

- Version the review policy and audition metadata. Upgrade stale review records
  once, using cached media, with visible progress; do not regenerate on polling.
- Under the new requested policy, restore old nonempty SKIP entries to Extras in
  unfinished, unapplied reviews, including persisted draft entries. Explain the
  change once: **Recovered 3 stems to Extras**. Retain other instrument choices,
  labels, lyric offsets, authored charts, source selections and target identity.
- This one-time migration deliberately treats ambiguous old SKIP values as
  recoverable audio, since the old format has no choice provenance. Explicit
  choices made after the upgrade remain explicit and survive future reloads.
- Preserve journals and revision checks. Never mutate a review while its Apply
  operation is in progress or unresolved. Reopening/refreshing a review must not
  invalidate authored chart drafts or silently overwrite changes from another
  browser.
- Already imported projects are unchanged by this plan. Recovering previously
  omitted media requires a deliberate stem reimport/rebuild from cached files;
  the current chart/click/level library update is not a stem recovery operation.

### 4. Make waveform scrubbing reliable and readable

- Finish the shared HTTP serving behavior: bounded/open-ended/suffix ranges,
  correct 206/416 headers, HEAD, valid MIME and disconnected-client handling.
  Reuse the already-tested recording-media range behavior where practical.
- Wait for metadata before applying a pending seek, clamp to the verified asset
  duration and display loading/seeking/error state beside the active player.
- Use the same verified duration for waveform clicks, displayed end time and
  cursor position. If browser metadata disagrees materially, flag/rebuild the
  preview instead of presenting an apparently accurate scrubber.
- Separate the static waveform from its moving cursor rather than loading a new
  image asynchronously on every time update. Repaint on resize and keep cursor
  updates tied to the current audio instance.
- Add a time readout for the scrub position, pointer/touch drag with pointer
  capture, and keyboard seeking. Opening another player stops the previous one;
  switching jobs closes it and rejects late metadata/results from the old job.
- Apply the same behavior to the lyric vocal player. Preserve ordinary play,
  pause and seek controls rather than inventing a separate audio interface.

## Acceptance before release

- Silence, low-level continuous audio, a single loud hit, sparse vocals/guitar,
  unmapped types, opposite-polarity stereo and a failed decode. Only actual
  silence is excluded automatically; other uncertain material reaches Extras.
- Verify the combined imported music retains the brief test bursts and matches
  the sum of all unique split stems within the output format's rounding tolerance.
- Reopen a pre-upgrade review containing SKIP entries and an authored chart; verify
  one-time recovery, new audio URLs, unchanged chart/offsets and durable new choices.
- Use the cached Fly Away originals as the real duration regression; no paid work.
  Also test a normal-duration song so the repair does not introduce a new offset.
- Known impulse/tone landmarks near the beginning, middle and end: compare browser
  audition at a seek target with decoded reference audio and its waveform. Checking
  `currentTime` alone does not prove the audible content is correctly located.
- Edge/Chromium and WebKit; desktop, narrow phone layout, cold metadata, rapid
  scrubbing, last stem, lyric vocal player and two queued songs. Confirm correct
  duration, no cross-job audio, and usable pause/seek after switching players.
- HTTP tests for first bytes, middle, tail, open-ended, suffix, out-of-range, HEAD
  and cancelled requests. Existing chart and recording audition must still pass.
- Native append/import check in a disposable project: correct song length, all
  expected destinations including Extras, and no duplicate parent/child audio.

Deliver code only after those checks, through both standard branches, with a new
release version and short migration notes. No room-library rebuild is automatic.
