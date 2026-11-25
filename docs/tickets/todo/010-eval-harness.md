# 010 — Eval harness + hand-written 50-prompt set

**Phase:** P2 · **Depends-on:** — · **Gate:** none

## Goal
A fixed eval that can rank training run N+1 against run N, written **before** the first real
training run.

## Why
Without this, "does it sound Singlish?" gets decided by reading a few outputs and feeling good,
which will mislead by run three. Three layers:

1. **Marker frequency** — generate on the fixed prompt set, compare marker distribution against
   the held-out human slice from 009. Too few markers = undertrained. Suspiciously *more* than
   humans use = overfit into self-parody, which is the classic dialect-LoRA failure and is
   invisible to a human skim.
2. **English regression** — plain instruction-following prompts, to catch catastrophic
   forgetting from stage 1.
3. **Human preference** — the private testers are ground truth.

## Scope
- `eval/prompts.yaml` — **50 hand-written prompts**, committed. Cover both varieties and
  several registers: casual chat, complaining, giving directions, food talk, asking for a
  favour, reacting to news. Tag each with its target `variety`.
- `eval/regression.yaml` — ~10 plain English instruction-following prompts with expected
  properties (follows the instruction, answers in English, no Singlish bleed where
  inappropriate).
- `scripts/eval.py --model <path>` → writes `eval/results/<run-id>.json` and a markdown summary:
  marker frequency per variety vs the human baseline, regression pass rate, and generation
  samples for human review.
- A `--compare <run-a> <run-b>` mode, because the whole point is ranking runs.

## Done-when
```sh
python3 -c "import yaml; \
p=yaml.safe_load(open('eval/prompts.yaml'))['prompts']; \
assert len(p)>=50, f'only {len(p)} prompts'; \
v={x['variety'] for x in p}; assert v=={'sg','my'}, v; \
r=yaml.safe_load(open('eval/regression.yaml'))['prompts']; assert len(r)>=10; \
print(len(p),'prompts,',len(r),'regression')" && \
test -f scripts/eval.py && echo ok
```

## Files
`eval/prompts.yaml`, `eval/regression.yaml`, `scripts/eval.py`

## Notes
The 50 prompts should be **drafted by an agent and reviewed by the user** — they are Malaysian
and will catch register mistakes no agent will. Flag them for review in the commit message.
