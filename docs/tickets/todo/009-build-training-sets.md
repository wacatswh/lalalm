# 009 — Build stage-1 corpus and stage-2 pair sets

**Phase:** P1 · **Depends-on:** 008 · **Gate:** none

## Goal
Emit the two artifacts training consumes: a flat text corpus for stage 1, and conversational
pairs for stage 2. Plus a dev slice small enough to live on the Mac.

## Why
The two training stages want different things. Stage 1 is register adaptation and eats flat
text. Stage 2 is behavioural and eats prompt→response pairs — which exist in the corpus
already, because 001/005 preserved `parent_uid`. This is where that decision pays off.

## Scope
- **Stage 1** → `data/processed/stage1.jsonl` (`{text}`): all items above the marker floor,
  weighted by `marker_score` (higher-density items may repeat). Target **20–50M tokens** —
  dialect adaptation via LoRA is cheap, this is not pretraining from scratch. Report the actual
  token count.
- **Stage 2** → `data/processed/stage2.jsonl` (`{prompt, response, variety}`): join each item to
  its `parent_uid`. Filter: response score above a threshold, both sides non-trivial length,
  response marker density above the floor. Target **10–30k pairs, balanced `sg`/`my`** — if
  `my` falls short, downsample `sg` rather than shipping an unbalanced set, and say so in the
  report.
- Held-out split for eval (010): ~2% of stage 1, stratified by variety. Never seen in training.
- **Dev slice** → a sampled subset capped at ~2 GB for the Mac, since the full corpus stays on
  firebat (invariant).

## Done-when
```sh
python3 scripts/build_sets.py --report && \
python3 -c "import json; \
s2=[json.loads(l) for l in open('data/processed/stage2.jsonl')]; \
assert len(s2)>=10000, f'only {len(s2)} pairs'; \
sg=sum(1 for r in s2 if r['variety']=='sg'); my=len(s2)-sg; \
r=min(sg,my)/max(sg,my); assert r>0.4, f'unbalanced sg={sg} my={my}'; \
assert all(r.get('prompt') and r.get('response') for r in s2); \
print(f'{len(s2)} pairs, sg={sg} my={my}, ratio={r:.2f}')"
```

## Files
`scripts/build_sets.py`

## Notes
If stage 2 cannot reach 10k balanced pairs, that is a **data** problem, not a build problem —
move this to `blocked/` with the actual counts and go back to 005 / more Manglish sources.
Do not lower the threshold to make the check pass.
