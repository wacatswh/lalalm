# 008 — Marker lexicon, density scoring, dedup, saturation report

**Phase:** P1 · **Depends-on:** 007 · **Gate:** none

## Goal
Score every item by dialect-marker density, dedup conservatively, and report per-variety
corpus saturation.

## Why
The obvious cleaning pipeline destroys this dataset. langid/fastText classifiers label Singlish
as either "English" — so a language filter keeps formal and colloquial posts equally — or as
low-confidence garbage, so a confidence threshold deletes precisely the most Singlish text in
the corpus. **Never gate on language ID** (invariant).

Instead score by marker density and use the score to *rank and weight*, keeping everything
above a very low floor. Same hazard with dedup: `lah`-heavy short replies look near-identical
to MinHash, so **exact-hash only, never near-dup** (invariant).

The saturation report is the stopping rule: when a source's rate of introducing unseen unigrams
and unseen markers falls to near zero, that register is saturated and more scraping is wasted.
Computed **per variety** — `sg` will saturate long before `my`, and a combined number would hide
exactly the Manglish shortfall this project is supposed to avoid.

## Scope
- `lexicon/markers.yaml` (repo root, tracked — `data/` is gitignored) — seed: `lah lor leh meh hor sia wah walao aiyo aiyah alamak
  bojio kena boleh tapi macam mana shiok sian paiseh chop blur kiasu makan tapau can-can
  got-got one-ah izzit`. Grouped by `sg` / `my` / `both`. **Extend this by reading real data**
  after 007 lands — the seed list is a starting point, not the finished lexicon.
- `scripts/score.py`: marker density (markers per token), length, score → `marker_score` field.
- Exact-hash dedup on normalized text (lowercase, collapse whitespace). Log how many dropped.
- `scripts/saturation.py`: per source, per variety — cumulative unseen-unigram and unseen-marker
  rate as items are consumed in scrape order. Write `docs/saturation.md` with a table and the
  verdict per source: `keep scraping` / `saturated`.

## Done-when
```sh
python3 scripts/score.py && python3 scripts/saturation.py && \
python3 -c "import json; \
rows=[json.loads(l) for l in open('data/processed/scored.jsonl')]; \
assert all('marker_score' in r for r in rows); \
sg=[r for r in rows if r['variety']=='sg']; my=[r for r in rows if r['variety']=='my']; \
assert sg and my, 'need both varieties present'; \
print('sg',len(sg),'my',len(my))" && \
test -f docs/saturation.md && grep -qi 'saturat' docs/saturation.md && echo ok
```

## Files
`lexicon/markers.yaml`, `scripts/score.py`, `scripts/saturation.py`, `docs/saturation.md`

## Notes
Only derived data belongs under `data/`; the lexicon is source, so it is tracked at the repo root.
