# 013 — Merge adapter, quantize to Q4_K_M GGUF

**Phase:** P4 · **Depends-on:** 012 · **Gate:** none

## Goal
Turn the trained adapter into one artifact firebat can serve.

## Why
llama.cpp can load a LoRA at runtime, but merging first is simpler, faster at inference, and
leaves **one file to ship** instead of a base-plus-adapter pair that can drift out of sync.
Q4_K_M on Qwen3-4B is ~2.5 GB of weights, which fits firebat's memory budget with room for KV
cache under the 5 Gi cap.

## Scope
- `scripts/export_gguf.sh`: merge stage-2 adapter into the stage-1-merged weights → convert to
  GGUF → quantize Q4_K_M.
- Produce **both** the 4B and the 1.7B GGUF. The 1.7B is the fallback: if 4B feels too slow in
  real tester use, swapping a file beats retraining (invariant).
- Record a checksum and the source adapter run-id alongside each GGUF, so a served model can
  always be traced back to the run that produced it.
- Re-run 010's eval **against the quantized model**, not just the unquantized one. Q4 can move
  marker frequency; if it degrades badly, try Q5_K_M and re-measure.

## Done-when
```sh
ls -la models/*.gguf && \
python3 -c "import json,glob; \
m=[json.load(open(f)) for f in glob.glob('models/*.json')]; \
assert m, 'no model manifests'; \
assert all('run_id' in x and 'sha256' in x for x in m); \
print([x['run_id'] for x in m])" && \
test -f eval/results/quantized-4b.json && echo ok
```

## Files
`scripts/export_gguf.sh`, `models/` (gitignored), `models/*.json` manifests (tracked)

## Notes
Add `models/*.gguf` to `.gitignore` — weights are not git's job — but **track the manifests**,
since they are the provenance record.
