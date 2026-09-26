# Fadr library: chart workflow audit

26 September 2026. Read-only research and an isolated layout dry run, before
application implementation. The main [implementation plan](UNIFIED_CHART_WORKFLOW_PLAN.md)
is revised using these findings.

## Coverage and method

- Read the configured Fadr account directly: 912 assets, including 48 non-deleted
  uploads with existing splits. Nathan excluded the three unnamed `source.wav`
  uploads. The remaining **45 recordings cover 44 song titles**: Bring Me To Life
  appears as two recordings of different lengths.
- Queried Ultimate Guitar for each named recording. Used the importer's default
  ordering (song/artist match, votes, then rating). Also inspected seven different
  higher-rated versions with at least 100 votes, plus the higher-rated but
  low-vote alternative for Jump. This is **53 recording/chart cases, 52 distinct
  chart URLs**. Ratings/counts are the values returned during this audit, not a
  permanent ranking or a claim that every version on UG was inspected.
- Jump required a corrected search: `Pointer Sisters / Jump For My Love`.
  The initial strict query returned nothing. An unrelated result from a relaxed
  exploratory search was rejected and excluded from all final measurements.
- Reused timing evidence in eight existing local jobs. For other recordings,
  queried the normal lyric-candidate search and inspected the closest available
  synchronized reference. These candidate choices exercise the proposed review
  workflow; they are not guaranteed to equal the existing automatic `/get`
  selection. Supplementary lookup probes are identified separately below.
- Ran the actual current chart parser and document generator on private copies.
  Then used headless Edge to measure an isolated prototype of the planned
  one-section-per-page layout at four computer/tablet sizes. It uses the current
  shared row wrapper, actual DOM heights, preferred 28/32px fonts and an 18px
  minimum. Content space is explicitly modelled as viewport minus 64px width
  and 180px height for controls/padding. This is a layout experiment, not final
  application CSS or completed scrolling-controller validation.
- Calculated tall-section scroll distances/rates against suggested section
  intervals. Ran isolated probes for retaining unheaded opening material and
  disabling automatic lyric-gap splitting. No production functions were edited.

No Fadr split tasks, uploads, import Apply, library updates, source replacements
or REAPER transport actions were performed. Full third-party chart/lyric text and
private source IDs remain in ignored local audit files, not in this report.

## Findings that change the implementation plan

### 1. Preserve the source before improving its presentation

The default [Boston chart](https://tabs.ultimate-guitar.com/tab/boston/more-than-a-feeling-chords-1050593)
contains only one explicit bracketed heading, Solo, well into the chart. The
current parser discards preceding material when any later recognized heading
exists. It retains 92 of 200 tagged chord occurrences. Parsing the unheaded
opening separately in an isolated probe retained all 200. The higher-rated
comparison also loses its opening through the same parser rule.

This is an existing parser bug, not a reason to reject those source charts.
Preserve unlabelled music as editable content with a neutral heading. Keep source
notes/chord dictionaries separately; do not blindly turn every preamble line
into an intro. Add source-to-document conservation checks so the UI can never
claim a complete chart while a musical passage has disappeared.

### 2. Headings, riffs and instructions need distinct treatment

The [Chain Reaction chart](https://tabs.ultimate-guitar.com/tab/john-farnham/chain-reaction-chords-648045)
puts its opening chords on the same line as its heading. The parser absorbs
markup into the heading and drops those four chords. [School's Out](https://tabs.ultimate-guitar.com/tab/alice-cooper/schools-out-chords-671962)
has similar inline riff labels/chords and embedded tablature. [Hold The Line](https://tabs.ultimate-guitar.com/tab/toto/hold-the-line-chords-1012428)
produces a spurious empty section named after an ASCII riff diagram.

The supplied `Bagpipes solo` heading in [You're the Voice](https://tabs.ultimate-guitar.com/tab/john-farnham/youre-the-voice-chords-1710600)
and `Sax Solo` in [The Best](https://tabs.ultimate-guitar.com/tab/tina-turner/the-best-chords-152012)
are not recognized as section boundaries. Taxiride's Get Set includes notation
and instructions inside a very large apparent intro.

Parse heading and same-line music separately. Recognize bracketed musical
headings beyond a small vocabulary. Preserve tablature as an optional fixed-width
notation block; distinguish it and performance instructions from sung lyric rows.
An unfamiliar heading must remain visible and editable. Do not invent chords
for a riff that the source represents only with tab.

### 3. Stop turning lyric gaps into compulsory sections

[Chasing Cars](https://tabs.ultimate-guitar.com/tab/snow-patrol/chasing-cars-chords-355425)
grows from **9 source sections to 17** generated sections, including empty
instrumental breaks inside verses. [Gold On The Ceiling](https://tabs.ultimate-guitar.com/tab/the-black-keys/gold-on-the-ceiling-chords-1146115)
grows from **12 to 21**, including pre-chorus fragments lasting about 1.5 seconds.
In isolated probes, disabling that automatic split returned them to 9 and 12
sections without losing any parsed rows.

Across the 45 default cases, 393 parsed source sections become 489 generated
sections. Some additions are useful missing intros; the count is not a claim
that every added section is wrong. Nevertheless, ordinary lyric gaps should be
timing evidence or optional break suggestions, not compulsory page changes.
Keep authored instrumental sections and offer Add section for genuine omissions.

### 4. Fit-to-page alone is insufficient

With the prototype's measured content area, **14 of 45 default cases have at
least one section that does not fit a 1024x768 tablet even at 18px**. There are
22 such sections. Examples include Can't Stop, Mr. Brightside, Bad, The Rock Show,
Get Lucky and Never Tear Us Apart. Some source blocks contain 16-28 paired rows.

| Viewport | Recordings with a section too large at 18px | Oversized sections |
| --- | ---: | ---: |
| Tablet landscape, 1024x768 | 14 / 45 | 22 |
| Tablet portrait, 768x1024 | 6 / 45 | 6 |
| Laptop, 1366x768 | 14 / 45 | 22 |
| Desktop, 1920x1080 | 5 / 45 | 5 |

These measurements use the current generated content, including the parser
limitations above; preserving missing content and removing spurious splits will
change the counts. They justify the fallback policy, not an exact final sizing
promise. Keep Scroll as the recommended reading mode and offer **Suggest splits**
for Pages. Proposals appear as ordinary section dividers for approval; they never
introduce an independent page-timing pass or silently discard text.

### 5. Validate timestamps, not just the lyric record's duration field

Five inspected timing sources contain timestamps beyond the Fadr recording:

| Song | Fadr recording | Last raw reference timestamp |
| --- | ---: | ---: |
| My People | 248.2s | 265.1s |
| Morning Glory | 256.9s | 303.1s |
| Jump (For My Love) | 266.6s | 380.2s |
| More Than a Feeling | 216.6s | 254.5s |
| Get Lucky | 248.7s | 315.7s |

These are raw evidence comparisons; existing explicit offsets must be considered
before final validity decisions. Jump is especially revealing: LRCLIB record
34525472 claims a 266-second duration while its line timestamps extend beyond
380 seconds. A near-perfect metadata duration match is therefore insufficient.

School's Out's nearest candidate differs from the Fadr recording by roughly
40 seconds. The older Bring Me To Life upload differs from its candidate by
about 10 seconds. These can indicate a different edit, extra video material or
bad timing data; this audit has not listened through those recordings to decide.
Long instrumental endings alone are not an error: a final lyric occurring early
must not be treated as proof of a mismatch.

Check timestamp bounds/order, source identity, text coverage and plausible
section intervals before using a timing source. Retain words and flag uncertain
timing. Never silently clip away late lyric references, compress a missing
passage into milliseconds, or stretch the entire reference to force a match.

### 6. Missing evidence must not cause runaway scrolling

The constrained candidate search initially returned no records for Chain Reaction
and Two Strong Hearts. With no lyric evidence, the current generator assigns
their first section an interval of only **0.05 seconds**. Chain Reaction's first
parsed block contains 32 rows. A naive tall-block interpolation in the prototype
would demand approximately **38,900 pixels/second**.

This is a concrete reason to revise the original proposal's unconditional
long-section interpolation. Untimed/suspect intervals need an explicit state;
hold the reading position or use manual navigation until a cue is supplied.
Make a one-pass Next section starts now workflow available. Automatic motion
must also have a tested sensible bound and stop when its timing assumptions fail.

Broader searches do find plausible Farnham references, but also unrelated tracks
from albums sharing the query name. Validate track and artist identity before
using a fallback. A failed exact search does not prove that no timed reference
exists. Supplementary probe results are recorded in the local evidence bundle.

The exact automatic `/get` check **succeeds for Chain Reaction**; its empty
candidate-search result is not an automatic-import failure. The zero-evidence
case above is a fallback stress test. For Two Strong Hearts, exact `/get` returned
404 and constrained search returned no candidates; the identity-checked broader
search found a reference matching 53 of 57 parsed word rows. The same broader
probe matched all 48 parsed word rows for Chain Reaction. Neither percentage is
an audible timing certification.

### 7. Chart ranking needs a usable-content check

Default popularity is a starting point. The Presets' My People candidate has
**no votes**. Jump's more-voted chart is **3.49 / 14 votes**, while its other
returned version is **4.82 / 6 votes**. Neither warrants automatic confidence.
The default Bring Me To Life source omits an intro; the locally chosen alternative
includes more instrumental material. Those are source differences, whereas the
Boston loss is a parser bug affecting both inspected versions.

Show rating and vote count beside a small content summary: sections, instrumental
material, formatting issues and timing coverage. Let the user preview an
alternative without destroying edits. Do not silently replace the chosen chart
because another version has a higher star score. Normalize artist articles and
meaningful title parentheses while preserving strict final identity checks.

### 8. Separate useful review warnings from routine unmatched text

The current generator reports review issues for almost every default case. An
unmatched performance instruction, repeated vocal aside and truly missing verse
should not all create the same attention burden. Supplied repeats and tablature
also require different handling from ordinary lyric rows.

Prioritize **content missing**, **wrong version/invalid timing**, **unplaced cue**
and **too much text for Pages**. Offer Next issue and identify the exact affected
section. Keep lower-confidence line matches as background evidence unless they
actually make a section cue or scrolling interval unreliable. Musical timing
still needs a listening check; text coverage percentages cannot certify it.

## Implementation order revised by the evidence

1. Expanded stem previews can still ship independently.
2. Add source-preservation/row-classification and reference-validation fixtures
   before renderer work. Include the Boston prelude, inline Farnham/Alice Cooper
   headings, compound solo headings, Jump's timestamp overrun and empty timing.
3. Implement the single section model with explicit unresolved timing and
   reversible legacy migration. Preserve source sections; make inferred gaps
   optional suggestions.
4. Build Pages/Scroll with fit warnings, suggested splits and bounded follow
   behaviour. No separate lyric/page timing state.
5. Complete the unified editor/import review and native persistence integration.
6. Run real playback checks and visual acceptance after implementation. This
   audit establishes structural/layout problems; it does not certify audible
   synchronization for 45 recordings.

## Per-recording audit

The table below covers every named Fadr upload. `Sections` means parsed source
sections -> sections produced by the current generator. `Too large` is the
number of resulting sections failing the proposed 18px tablet-landscape fit.
Zero is a layout result, not a certification that the chart is complete or timed
correctly. Chart links point to the inspected default, except Jump, which required
the identity-checked search correction described above.

| Recording | Duration | UG rating / votes | Sections | Too large | Main review point |
| --- | ---: | ---: | ---: | ---: | --- |
| [Alannah Myles - Black Velvet](https://tabs.ultimate-guitar.com/tab/alannah-myles/black-velvet-chords-136463) | 4:50 | 4.79 / 1,089 | 7 ? 15 | 0 | Check inferred gaps/section starts |
| [Alice Cooper - School's Out](https://tabs.ultimate-guitar.com/tab/alice-cooper/schools-out-chords-671962) | 4:33 | 4.77 / 170 | 15 ? 16 | 0 | Inline riff/tab parsing; timing candidate differs by 40s |
| [Blink 182 - All The Small Things](https://tabs.ultimate-guitar.com/tab/blink-182/all-the-small-things-chords-118610) | 2:50 | 4.80 / 2,358 | 10 ? 10 | 0 | Check inferred gaps/section starts |
| [Blink 182 - The Rock Show](https://tabs.ultimate-guitar.com/tab/blink-182/the-rock-show-chords-1171376) | 2:51 | 4.80 / 218 | 11 ? 12 | 3 | Three chorus blocks exceed tablet fit |
| [Boston - More Than a Feeling](https://tabs.ultimate-guitar.com/tab/boston/more-than-a-feeling-chords-1050593) | 3:36 | 4.80 / 1,039 | 1 ? 6 | 1 | Opening music lost before first heading; raw timing overrun |
| [Coldplay - Yellow](https://tabs.ultimate-guitar.com/tab/coldplay/yellow-chords-114080) | 4:32 | 4.87 / 25,224 | 9 ? 16 | 0 | Check inferred gaps/section starts |
| [Daft Punk - Get Lucky](https://tabs.ultimate-guitar.com/tab/daft-punk/get-lucky-chords-1239950) | 4:08 | 4.83 / 2,189 | 10 ? 10 | 3 | Large repeated blocks; raw timing overrun |
| [Eskimo Joe - Black Fingernails, Red Wine](https://tabs.ultimate-guitar.com/tab/eskimo-joe/black-fingernails-red-wine-chords-455065) | 3:56 | 4.68 / 27 | 8 ? 9 | 0 | Check inferred gaps/section starts |
| [Evanescence - Bring Me To Life](https://tabs.ultimate-guitar.com/tab/evanescence/bring-me-to-life-chords-662308) | 4:03 | 4.83 / 690 | 9 ? 13 | 0 | Default source has no intro; compare recording versions |
| [Evanescence - Bring Me To Life ft. Paul McCoy](https://tabs.ultimate-guitar.com/tab/evanescence/bring-me-to-life-chords-662308) | 4:13 | 4.83 / 690 | 9 ? 11 | 0 | Default source has no intro; compare recording versions |
| [Fleetwood Mac - Dreams](https://tabs.ultimate-guitar.com/tab/fleetwood-mac/dreams-chords-43918) | 4:17 | 4.84 / 4,191 | 6 ? 7 | 0 | Check inferred gaps/section starts |
| [Greta Van Fleet - Black Smoke Rising](https://tabs.ultimate-guitar.com/tab/greta-van-fleet/black-smoke-rising-chords-2448191) | 4:19 | 4.91 / 422 | 11 ? 15 | 0 | Check inferred gaps/section starts |
| [INXS - Never Tear Us Apart](https://tabs.ultimate-guitar.com/tab/inxs/never-tear-us-apart-chords-21372) | 3:51 | 4.84 / 2,287 | 9 ? 10 | 1 | Long final chorus; preserve intentional breaks |
| [John Farnham - Chain Reaction](https://tabs.ultimate-guitar.com/tab/john-farnham/chain-reaction-chords-648045) | 3:13 | 4.86 / 43 | 3 ? 4 | 2 | Inline heading drops chords; candidate search empty, exact lookup works |
| [John Farnham - Two Strong Hearts](https://tabs.ultimate-guitar.com/tab/john-farnham/two-strong-hearts-chords-1233901) | 3:40 | 4.73 / 66 | 10 ? 10 | 1 | Exact lookup fails; broader lookup succeeds; long final chorus |
| [John Farnham - You're the Voice](https://tabs.ultimate-guitar.com/tab/john-farnham/youre-the-voice-chords-1710600) | 5:11 | 4.84 / 232 | 6 ? 11 | 1 | Bagpipes solo heading not recognized |
| [Lenny Kravitz - Fly Away](https://tabs.ultimate-guitar.com/tab/lenny-kravitz/fly-away-chords-51423) | 3:42 | 4.80 / 457 | 8 ? 9 | 1 | Long outro; check reference and repeated content |
| [Maneskin - Beggin](https://tabs.ultimate-guitar.com/tab/3732140) | 3:33 | 4.86 / 2,153 | 10 ? 12 | 1 | Large block needs Pages split or Scroll |
| [Mark Ronson ft. Amy Winehouse - Valerie](https://tabs.ultimate-guitar.com/tab/mark-ronson/valerie-chords-738108) | 4:40 | 4.88 / 6,778 | 6 ? 9 | 0 | Limited word-match coverage; check arrangement |
| [Michael Jackson - Bad](https://tabs.ultimate-guitar.com/tab/michael-jackson/bad-chords-258772) | 4:05 | 4.72 / 91 | 13 ? 13 | 1 | 28-row final chorus; unsuitable for one tablet page |
| [Oasis - Morning Glory](https://tabs.ultimate-guitar.com/tab/oasis/morning-glory-chords-443013) | 4:16 | 4.86 / 531 | 8 ? 8 | 0 | Reference timestamps exceed recording |
| [Paramore - Misery Business](https://tabs.ultimate-guitar.com/tab/paramore/misery-business-chords-531366) | 3:19 | 4.87 / 1,336 | 10 ? 11 | 0 | Instrumental/vocal heading ambiguity; preserve raw source |
| [Paramore - Still into You _ Lyrics](https://tabs.ultimate-guitar.com/tab/paramore/still-into-you-chords-1231873) | 3:36 | 4.91 / 2,558 | 7 ? 9 | 0 | Check inferred gaps/section starts |
| [Rage Against The Machine - Bulls On Parade](https://tabs.ultimate-guitar.com/tab/rage-against-the-machine/bulls-on-parade-chords-846911) | 3:53 | 4.28 / 31 | 6 ? 14 | 0 | Check inferred gaps/section starts |
| [Red Hot Chili Peppers - Can't Stop](https://tabs.ultimate-guitar.com/tab/red-hot-chili-peppers/cant-stop-chords-792862) | 4:37 | 4.89 / 2,267 | 7 ? 9 | 3 | 16-22-row verses; offer smaller blocks |
| [Simply Red - Stars](https://tabs.ultimate-guitar.com/tab/simply-red/stars-chords-1058451) | 4:05 | 4.84 / 289 | 8 ? 8 | 0 | Good uncomplicated example; preserve source notes separately |
| [Snow Patrol - Chasing Cars](https://tabs.ultimate-guitar.com/tab/snow-patrol/chasing-cars-chords-355425) | 4:26 | 4.83 / 8,372 | 9 ? 17 | 0 | Five inferred empty breaks; 9 source sections become 17 |
| [Steve Winwood - Higher Love](https://tabs.ultimate-guitar.com/tab/steve-winwood/higher-love-chords-1740586) | 4:13 | 4.84 / 318 | 7 ? 8 | 0 | Check inferred gaps/section starts |
| [Stevie Nicks - Edge of Seventeen](https://tabs.ultimate-guitar.com/tab/stevie-nicks/edge-of-seventeen-chords-278205) | 8:33 | 4.82 / 569 | 13 ? 15 | 0 | 8:33 recording; verify extended arrangement/tail |
| [Taxiride - Get Set](https://tabs.ultimate-guitar.com/tab/taxiride/get-set-chords-1811077) | 3:05 | 4.90 / 22 | 8 ? 11 | 1 | Notation/instructions inflate intro block |
| [The Black Keys - Gold On The Ceiling](https://tabs.ultimate-guitar.com/tab/the-black-keys/gold-on-the-ceiling-chords-1146115) | 3:45 | 4.82 / 837 | 12 ? 21 | 1 | Extra lyric-gap splits; short fragments |
| [The Black Keys - Lonely Boy](https://tabs.ultimate-guitar.com/tab/the-black-keys/lonely-boy-chords-1120149) | 3:15 | 4.84 / 2,190 | 8 ? 11 | 0 | Check inferred gaps/section starts |
| [The Darkness - I Believe in a Thing Called Love](https://tabs.ultimate-guitar.com/tab/the-darkness/i-believe-in-a-thing-called-love-chords-1416874) | 3:35 | 4.72 / 241 | 13 ? 13 | 0 | Compact sections fit; several instrumental cues need review |
| [The Fratellis - Chelsea Dagger](https://tabs.ultimate-guitar.com/tab/the-fratellis/chelsea-dagger-chords-641973) | 3:49 | 4.82 / 516 | 9 ? 9 | 0 | Mostly usable structure; review suggested starts |
| [The Killers - Mr. Brightside](https://tabs.ultimate-guitar.com/tab/the-killers/mr-brightside-chords-202646) | 3:47 | 4.88 / 9,151 | 10 ? 10 | 2 | Long verses; offer smaller blocks |
| [The Only Ones - Another Girl, Another Planet](https://tabs.ultimate-guitar.com/tab/the-only-ones/another-girl-another-planet-chords-47890) | 2:59 | 4.76 / 136 | 10 ? 10 | 0 | Mostly usable structure; review suggested starts |
| [The Pointer Sisters - Jump (For My Love)](https://tabs.ultimate-guitar.com/tab/pointer-sisters/jump-for-my-love-chords-2081577) | 4:26 | 3.49 / 14 | 9 ? 9 | 0 | Search correction required; raw timing extends to 380s |
| [The Presets - My People](https://tabs.ultimate-guitar.com/tab/the-presets/my-people-chords-6590783) | 4:08 | 0.00 / 0 | 10 ? 10 | 0 | Unrated chart; raw timing overrun |
| [The Temper Trap - Sweet Disposition](https://tabs.ultimate-guitar.com/tab/the-temper-trap/sweet-disposition-chords-992955) | 3:54 | 4.84 / 276 | 7 ? 8 | 0 | Check inferred gaps/section starts |
| [Tina Arena - Burn](https://tabs.ultimate-guitar.com/tab/tina-arena/burn-chords-137338) | 4:21 | 4.83 / 83 | 8 ? 11 | 0 | Check inferred gaps/section starts |
| [Tina Turner - The Best](https://tabs.ultimate-guitar.com/tab/tina-turner/the-best-chords-152012) | 4:09 | 4.81 / 558 | 7 ? 7 | 0 | Sax Solo heading not recognized |
| [Toto - Africa](https://tabs.ultimate-guitar.com/tab/toto/africa-chords-87063) | 4:31 | 4.84 / 3,418 | 8 ? 10 | 0 | Check inferred gaps/section starts |
| [Toto - Hold The Line](https://tabs.ultimate-guitar.com/tab/toto/hold-the-line-chords-1012428) | 3:58 | 4.73 / 614 | 8 ? 11 | 0 | Riff diagram becomes an empty section |
| [Toto - Rosanna](https://tabs.ultimate-guitar.com/tab/toto/rosanna-chords-1415422) | 5:31 | 4.84 / 363 | 8 ? 9 | 0 | Check inferred gaps/section starts |
| [Wheatus - Teenage Dirtbag](https://tabs.ultimate-guitar.com/tab/wheatus/teenage-dirtbag-chords-927822) | 4:06 | 4.86 / 3,913 | 12 ? 12 | 0 | Mostly usable structure; review suggested starts |

## Alternative charts inspected

These were comparisons, not automatic replacements. Rows describe parsed content;
they do not establish musical accuracy or timing quality.

| Song / alternative | Rating / votes | Parsed sections / rows | Review implication |
| --- | ---: | ---: | --- |
| [Maneskin - Beggin](https://tabs.ultimate-guitar.com/tab/4160128) | 4.87 / 120 | 12 / 62 | Compare source completeness and fit before choosing |
| [Fleetwood Mac - Dreams](https://tabs.ultimate-guitar.com/tab/fleetwood-mac/dreams-chords-1414778) | 4.87 / 304 | 10 / 61 | Compare source completeness and fit before choosing |
| [Blink 182 - All The Small Things](https://tabs.ultimate-guitar.com/tab/blink-182/all-the-small-things-chords-1173088) | 4.85 / 576 | 8 / 46 | Compare source completeness and fit before choosing |
| [Toto - Africa.wav](https://tabs.ultimate-guitar.com/tab/toto/africa-chords-1744555) | 4.86 / 1,366 | 7 / 42 | Compare source completeness and fit before choosing |
| [Coldplay - Yellow.m4a](https://tabs.ultimate-guitar.com/tab/coldplay/yellow-chords-1986679) | 4.91 / 137 | 9 / 30 | Compare source completeness and fit before choosing |
| [The Pointer Sisters - Jump (For My Love).m4a](https://tabs.ultimate-guitar.com/tab/pointer-sisters/jump-for-my-love-chords-4949461) | 4.82 / 6 | 10 / 46 | Higher star score, only six votes; more written material |
| [Alannah Myles - Black Velvet.m4a](https://tabs.ultimate-guitar.com/tab/alannah-myles/black-velvet-chords-1820502) | 4.80 / 136 | 8 / 35 | Compare source completeness and fit before choosing |
| [Boston - More Than a Feeling.m4a](https://tabs.ultimate-guitar.com/tab/boston/more-than-a-feeling-chords-1242524) | 4.87 / 149 | 1 / 9 | Opening-loss parser bug also affects this version |

## Local evidence and reproducibility

Ignored folder: `imports/.visual/unified-chart-audit-20260926/`.

- `fadr-library.json`: filtered account inventory, without API credentials.
- `fetch_audit.py`, per-upload JSON: source retrieval and cached private content.
- `analyse_audit.py`, `analysis.json`: parser/alignment and 212 browser viewport
  measurements (53 cases x four sizes), including tall-section geometry.
- `improvement-probes.json`: isolated prelude/gap experiments.
- `timing-search-probes.json`: supplementary missing-reference lookups.

All 53 cases generated a document and completed the four layout measurements
without a build/layout exception. That technical success did not detect the
musical content loss by itself; the source-conservation and plausibility checks
are essential additions. Downloaded charts are kept private and are not public
test fixtures. Public regression tests should use small synthetic equivalents.
