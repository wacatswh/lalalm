# 017 — Teach target vocabulary via synthetic pairs (the Dissy register)

**Phase:** P1 · **Depends-on:** 009 · **Gate:** none (user review of drafted pairs)

## Goal
Make the model actually use a named set of words. The user asked for the Ah Beng /
lala-zai register from 低清DISSY — "steady bom bibi", "tokong", "kennot", "don't play
play", "ah beng", "lala zai".

## Why
Weighting cannot do this, and the numbers say so. Measured against the 60,139-row
corpus:

| term | occurrences |
|---|---|
| `settle` | 117 |
| `kopitiam` | 46 |
| `siapa` | 27 |
| `mamak` | 16 |
| `ah beng` / `lala` | 15 each |
| `tokong` | **2** |
| `steady bom` / `bom bibi` / `kennot` | **1 each** |
| `otai` | **0** |

`marker_score` upweighting works for the top rows — there is real text to upweight.
It cannot work for the signature phrases: **you cannot upweight something that appears
once in sixty thousand rows.** No weighting scheme produces a model that says "steady
bom bibi" if the corpus effectively never does.

The source videos cannot supply it either. Of the four URLs given, **two have no
subtitles at all** (including the 9:46 comedy sketch, the most valuable one), one has
ASR only, and one has manual `zh-Hant` lyrics. Total extractable text is a few hundred
words — not a corpus, and the lyrics are copyrighted besides.

The remaining mechanism is the standard one for teaching specific vocabulary to an
instruct model: **a small set of hand-written prompt→response pairs that use the target
terms naturally**, mixed into stage 2 at a modest ratio.

## Scope
- `data/seed/vocab_pairs.yaml` (tracked — this is source, not scraped data): 100–200
  prompt→response pairs, each using one or more target terms in natural conversational
  context. Draft by agent, **reviewed by the user** — they are Malaysian and will catch
  misuse that an agent cannot.
- Terms list drawn from `lexicon/markers.yaml` `my` section plus the Dissy additions.
- Mix into stage 2 in `build_sets.py` at a capped ratio (start ~5–10% of pairs) so the
  model learns the vocabulary without the synthetic register dominating real text.
- Eval: add a `vocab` scenario to `eval/prompts.yaml` whose prompts invite these terms,
  and assert in `scripts/eval.py` that target-term frequency rises relative to baseline.
  Watch the existing self-parody guard — forcing vocabulary is exactly how a model tips
  into caricature.

## Done-when
```sh
.venv/bin/python -c "
import yaml
p=yaml.safe_load(open('data/seed/vocab_pairs.yaml'))['pairs']
assert len(p)>=100, len(p)
terms={'tokong','steady bom','bom bibi','kennot','ah beng','lala'}
covered={t for t in terms for x in p if t in (x['response']+x['prompt']).lower()}
assert covered==terms, f'uncovered: {terms-covered}'
print(f'{len(p)} pairs, all {len(terms)} signature terms covered')"
```

## Notes — a structural gap this exposed
`scripts/markers.py` tokenises with `[A-Za-z']+`, i.e. **Latin script only**. 低清DISSY's
content is Mandarin-dominant Malaysian Chinese with Manglish mixed in; its video titles
are mostly Chinese. So the scorer, the saturation report and the eval are all blind to
CJK text. If the target register is genuinely Malaysian *Chinese* code-switching rather
than Malay-English Manglish, that is a larger change than this ticket: tokenisation,
lexicon and eval would all need CJK support. Raise it before collecting Chinese sources.
