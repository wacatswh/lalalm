# 016 — YouTube auto-captions are unsuitable for dialect corpus

**Phase:** P1 · **Depends-on:** — · **Gate:** none

## Goal
Decide whether the YouTube path can be salvaged, and restrict it to manual subtitles
if so. Right now it should stay off.

## Why
Measured on 2 episodes of `@yahlahbut`, a Singaporean comedy podcast — about the most
Singlish-dense spoken source imaginable. Result: **6,771 cues, 38,450 tokens, and
0% of rows contained a single dialect marker** (mean `marker_score` 0.0002; the only
hits were `damn` ×6). The same scorer finds markers in 5% of Lowyat forum rows.

The cause is structural, not a tuning problem: **these are ASR auto-captions, and ASR
normalises dialect to standard English.** `yt-dlp --list-subs` reports only
"Available automatic captions" for the sampled video — no human-authored track. A
Singaporean comedian's speech is transcribed as *"I really applaud the resilience
that you guys have to keep this going"*. Whatever Singlish was spoken, the
transcription layer removes it. Collecting more hours cannot fix this.

Two further defects found in the same sample, which matter if this path is ever revived:

1. **The non-English tracks are machine translations, not speech.** The sample pulled a
   `ta` (Tamil) track with 3,010 cues — YouTube auto-translates auto-captions into every
   language. Ticket 004's design interleaves language tracks by timestamp to preserve
   code-switching; with auto-captions that premise is false, and the interleaving
   actively poisons the corpus by implying speakers code-switch into machine
   translations of their own sentences. The premise only holds for *manual* multi-track
   subtitles.
2. **80% of cues repeat their predecessor's tail** (rolling-window captions), and 1,474
   cues contain undecoded HTML entities (`&gt;`). 004's consecutive-exact-duplicate
   collapse does not catch overlapping windows.

## Scope
Decide one of:
- **(a) Park it** — leave the YouTube sources `enabled: false` and spend the effort on
  015 instead. Recommended: the ceiling here is low even if the bugs are fixed.
- **(b) Manual subtitles only** — drop `--write-auto-sub`, keep `--write-sub`, and
  accept that very few videos qualify. If taken, also fix: de-overlap rolling windows,
  `html.unescape` the text, and restrict `--sub-langs` to tracks that are not
  auto-translated.

Do not simply fix the bugs and re-enable: the bugs are not why the density is zero.

## Done-when
Either the YouTube entries in `sources.yaml` are `enabled: false` with this ticket
referenced (option a), or:
```sh
.venv/bin/python scripts/scrape_youtube_captions.py <manual-sub video> && \
.venv/bin/python scripts/ingest.py && .venv/bin/python scripts/score.py && \
.venv/bin/python -c "
import json
rows=[json.loads(l) for l in open('data/processed/scored.jsonl')]
yt=[r for r in rows if r['source']=='youtube']
withm=sum(1 for r in yt if r['marker_count'])/len(yt)
assert withm > 0.03, f'still only {withm:.1%} of caption rows carry a marker'
print('ok')"
```

## Files
`scripts/scrape_youtube_captions.py`, `sources.yaml`

## Notes
`data/raw/youtube/adhoc.jsonl.quarantine` holds the test scrape. Not deleted — it is
the evidence for this ticket. `ingest.py` skips it because it does not end in `.jsonl`.
