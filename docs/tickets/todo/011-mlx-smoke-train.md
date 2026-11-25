# 011 — MLX two-stage LoRA smoke train on Qwen3-1.7B

**Phase:** P2 · **Depends-on:** 009, 010 · **Gate:** none

## Goal
Run the complete two-stage pipeline end to end on the M1, for free, on the small model rung.

## Why
This is the ticket that de-risks everything paid. Every mistake that would otherwise be
discovered on a billed GPU — wrong chat template, a stage-2 file the loader rejects, an eval
that crashes at the end of a four-hour run — surfaces here at zero cost. 1.7B is enough to prove
the *pipeline*; it is not expected to be good.

## Scope
- `HF_HOME` set to an explicit path (invariant — the default cache keeps both the original
  download and the MLX-converted copy, which is how 58 GB becomes 20 GB).
- Pull the dev slice from firebat, not the full corpus.
- **Stage 1**: r=8, LR ~2e-5, target q/k/v/o only, 1 epoch over the stage-1 slice.
- **Merge** stage 1 into the weights.
- **Stage 2**: r=16–32, LR ~1e-4, target attention + MLP, 2–3 epochs over the pairs.
- Run 010's eval after each stage separately — merging between stages exists precisely so
  stage 1 can be judged on its own.
- `scripts/train_mlx.sh` capturing the exact commands, and `docs/training.md` recording what
  the two stages did to the metrics.

## Done-when
```sh
test -f eval/results/smoke-stage1.json && test -f eval/results/smoke-stage2.json && \
python3 -c "import json; \
s1=json.load(open('eval/results/smoke-stage1.json')); \
s2=json.load(open('eval/results/smoke-stage2.json')); \
assert s2['regression_pass_rate'] > 0.5, 'catastrophic forgetting'; \
print('stage1 markers', s1['marker_freq'], '-> stage2', s2['marker_freq'])"
```
The bar is **the pipeline ran and the eval produced comparable numbers**, not that 1.7B is good.

## Files
`scripts/train_mlx.sh`, `docs/training.md`

## Notes
Verify the exact Qwen3 HF repo IDs and current instruct naming at implementation time rather
than trusting a remembered string. **Instruct, never Base** (invariant).

The M1 Air is fanless — expect thermal throttling on long runs. Not a problem for a smoke test;
it is one reason real runs go to Modal.
