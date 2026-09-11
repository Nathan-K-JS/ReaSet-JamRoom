# Shared generation and compressed upload review

Importer release: `v3.2`. Chart generator: `source-pages-3`.

The earlier source-page work preserved authored chord columns, but that was not
enough to certify useful output. A perfect text match does not establish section
boundaries, recording alignment, musical correctness or readable pagination.
There are no artist/title-specific rules in this release.

## Generation changes

- Preserve every source row occurrence, word and chord column, including when
  sections are regrouped. Keep original source templates for comparison.
- Detect lyrics under instrumental headings. Split any leading chord-only
  passage from the vocals. Name the vocals after a repeated source passage only
  when the whole passage strongly matches and the section family is unambiguous;
  otherwise use “Vocal section”. Report the inference for review.
- Do not give an internal instrumental passage a standalone section lasting
  less than two seconds. Keep its rows with the preceding section and report the
  boundary for editing. This is a display fallback, not a newly verified timing.
- Check coverage in both directions: an exact match of all chart words can still
  omit words/passages present in the timed recording lyrics.
- Show review notes in the importer and section editor. Matching counts are
  diagnostics, never a readiness score. Automatically generated cues remain
  estimated even when all words match.
- Minimise page count before balancing space, keeping wrapped lyric rows together
  when they fit. The previous approximate balancing could create an extra page
  containing only a transition riff.

Fresh imports, cached reimports and **Update whole library** use the same
`prepare_chart_document` / `build_document` path. The generator version bump makes
older documents eligible for the explicit update chooser. Existing manual-edit
protection and backups remain in force. No saved library is silently regenerated.

## Verification on the testing workstation

- 93 automated tests passed, including missing headings, missing recording
  passages, source fidelity, uncertain gaps, pagination, actual browser controls,
  bulk selection/protection and compressed/legacy upload contracts.
- Rebuilt cached Paramore, Blink, Dreams and Darkness documents without modifying
  their saved jobs. All pages passed clipping checks at 1440×1000, 768×1024,
  390×844 and 1024×768. Local evidence: `imports/.visual/source-pages-3/`.
- Paramore's unlabeled repeated chorus was identified. Unsupported short
  instrumental boundaries were caught in both Paramore and Blink. Dreams and
  Darkness retained their section structure.
- Imported regenerated Paramore into a real REAPER scratch project: six stems,
  51 lyric items, 141 measured chord items. Visually inspected the chord/lyric
  display and section editor. Section split and timing tap saved through the
  real bridge; original project remained unchanged. Local evidence:
  `imports/.visual/song-c_64ge6l/`.
- Paramore uses 11 desktop/tablet pages. The transition riff stays beneath the
  end of the verse. The phone layout still needs 30 pages: fitting without
  clipping does not make a small phone ideal for this song.

These checks do not verify every chord by ear or every cue against playback.
Instrumental entrances without independent timing evidence still need taps;
incorrect or incomplete source charts still need review. The method now makes
those limitations explicit instead of equating successful generation with a
musically approved result.

## Audio transfer

New YouTube downloads prefer native M4A and upload that compressed file. Only
sources without M4A require conversion. Fadr upload names, extensions and MIME
types now follow the actual file format. Existing cached WAV jobs remain usable.
Cache detection, resumed preparation and explicit audio deletion handle both
formats. Local REAPER stem preparation continues using decoded WAVs.

A fresh download of the cached Dreams recording took **8.61 seconds**, producing
**4,166,901 bytes**, versus the existing **49,448,554-byte WAV**: **91.6% fewer
upload bytes**. This is a measured download and size comparison, not a controlled
before/after speed comparison. No paid split was run to benchmark cloud processing.
Download elapsed time is persisted and upload elapsed time is logged separately
from the existing Fadr task-wait logs.

YouTube already transfers compressed audio; expanding it to WAV before uploading
was avoidable. Smaller uploads should reduce transfer time, but do not establish
a speedup in Fadr's separation models. Cached Fadr stem payloads are already MP3
data even though the provider download path used `.wav` names; decoding those
locally is separate from network transfer.

Primary format references: [Fadr supported uploads](https://fadr.com/help/stems),
[Fadr API upload contract](https://fadr.com/docs/api-stems-tutorial).

Delivery is through the normal jam-room update branch. On the separate jam-room
PC, run **JamRoom Update.bat**, reload ReaSet, and use the importer’s explicit
library update chooser. Test-workstation imports do not update that PC's library.
