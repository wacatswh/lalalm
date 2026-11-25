# 015 — Dialect-dense discovery: target boards, weight by thread density

**Phase:** P1 · **Depends-on:** 008 · **Gate:** none

## Goal
Stop collecting rows that contain no dialect, by choosing *which* threads to scrape
instead of taking whatever the recency feed offers.

## Why
Measured, not guessed. From the first 172 Lowyat threads (14,791 scored rows):

- mean `marker_score` **0.0042**, and only **5% of rows contain a single marker**
- only **34 of 122** threads have mean density above 0.01
- the density is inversely related to thread size: the densest threads are short
  (8 posts, mean 0.105) while the largest (355 posts, 160 posts) score **0.0000**

So a handful of enormous hardware/trading mega-threads dominate the row count and
dilute everything. `scripts/mine_lexicon.py` on this corpus surfaced `iphone`,
`logitech`, `steelseries`, `oled`, `motul`, `tesla`, `shopee` — product talk in plain
English — rather than dialect. Training stage 1 on this as-is would spend most of its
token budget learning to write neutral English about graphics cards.

This is the saturation report doing its job: it says the discovery strategy is wrong,
not that the corpus is finished.

## Scope
1. **Board-targeted discovery.** `scripts/scrape_lowyat.py` now records `board` from
   the navstrip, so `docs/saturation.md` gets a per-board table. Scrape a small sample
   across boards, read that table, and add a `boards` allowlist to the Lowyat entry in
   `sources.yaml` (Kopitiam and similar chat boards; exclude the hardware and trading
   boards). Rows collected before board recording existed carry `board: null`.
2. **Thread-level density gate at discovery time.** After parsing a thread, if its mean
   `marker_score` is below a floor, log it to a `.skipped` file and do not write its
   posts. Cheaper than filtering later, and it stops megathreads from dominating.
3. **Length-aware weighting in 009.** Even within a good board, cap the number of rows
   any single thread contributes, so one 355-post thread cannot outweigh forty short
   dialect-dense ones.

Keep the floor **low** and weight rather than hard-filter wherever possible — the
project invariant is to rank, not gate. The gate here is on *threads*, which are
cheap to re-fetch, not on individual utterances.

## Done-when
```sh
.venv/bin/python scripts/score.py && .venv/bin/python scripts/saturation.py && \
.venv/bin/python -c "
import json
rows=[json.loads(l) for l in open('data/processed/scored.jsonl')]
my=[r for r in rows if r['variety']=='my']
withm=sum(1 for r in my if r['marker_count'])/len(my)
mean=sum(r['marker_score'] for r in my)/len(my)
print(f'my: {len(my)} rows, mean {mean:.4f}, {withm:.0%} with marker')
assert withm > 0.25, f'only {withm:.0%} of rows carry a marker (was 5%)'
assert mean > 0.015, f'mean density {mean:.4f} still too low (was 0.0042)'
print('ok')"
```

## Files
`sources.yaml`, `scripts/scrape_lowyat.py`, `scripts/build_sets.py`

## Notes
Do not delete the already-collected low-density rows. They are harmless as stage-1
filler at low weight, and re-fetching costs Lowyat bandwidth for no gain.
