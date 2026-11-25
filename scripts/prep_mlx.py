#!/usr/bin/env python3
"""Convert stage1/stage2 into the {train,valid}.jsonl layout mlx_lm.lora expects.

Stage 1 uses the `text` format (raw continued-pretraining style) and stage 2 uses the
`messages` chat format, so stage 2 trains through the model's own chat template --
which is the point of starting from the instruct model rather than Base.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
OUT = ROOT / "data" / "mlx"
VALID_FRAC = 0.03
SEED = 1337
# Stage-1 rows are forum posts: median ~18 tokens, p95 ~127. Feeding them one per
# sequence at max_seq_length 512 means training almost entirely on padding -- measured
# at ~168 real tokens per iteration, so 800 iters saw ~6% of one epoch. Packing
# concatenates short rows up to a budget, which is standard for continued pretraining
# and raises tokens/step by roughly 25x. Stage 2 is NOT packed: each pair is one
# training example and must stay separate.
PACK_TOKENS = 480
SEP = "\n\n"


def pack(texts: list[str], budget: int = PACK_TOKENS) -> list[dict]:
    """Greedily concatenate short texts up to a word-count budget."""
    out, buf, n = [], [], 0
    for t in texts:
        w = max(int(len(t.split()) * 1.3), 1)   # rough token estimate
        if buf and n + w > budget:
            out.append({"text": SEP.join(buf)})
            buf, n = [], 0
        buf.append(t)
        n += w
    if buf:
        out.append({"text": SEP.join(buf)})
    return out


def write(rows: list[dict], d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    rng.shuffle(rows)
    n = max(int(len(rows) * VALID_FRAC), 8)
    for name, part in (("valid", rows[:n]), ("train", rows[n:])):
        with (d / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for r in part:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  {d.name}: {len(rows) - n} train, {n} valid")


def main() -> None:
    s1 = [json.loads(l) for l in (PROC / "stage1.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    texts = [r["text"] for r in s1 if r.get("text")]
    packed = pack(texts)
    est = sum(len(x["text"].split()) * 1.3 for x in packed)
    print(f"  stage1 packed: {len(texts)} rows -> {len(packed)} sequences "
          f"(~{est / max(len(packed), 1):.0f} est. tokens each, {est:,.0f} total)")
    write(packed, OUT / "stage1")

    s2 = [json.loads(l) for l in (PROC / "stage2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    write([{"messages": [{"role": "user", "content": r["prompt"]},
                         {"role": "assistant", "content": r["response"]}]}
           for r in s2 if r.get("prompt") and r.get("response")], OUT / "stage2")


if __name__ == "__main__":
    main()
