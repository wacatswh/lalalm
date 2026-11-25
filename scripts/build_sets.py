#!/usr/bin/env python3
"""Emit the two artifacts training consumes, plus a held-out eval baseline.

  stage1.jsonl   flat text for register adaptation   {text}
  stage2.jsonl   conversational pairs for behaviour  {prompt, response, variety, src}
  holdout.jsonl  never trained on; eval.py's human baseline

Three things here are load-bearing:

  * PER-THREAD CAP. One 355-post megathread must not outweigh forty short
    dialect-dense threads. Without this, corpus averages are set by thread length
    rather than by language.
  * MARKER WEIGHTING, NOT FILTERING. High-density rows are repeated in stage 1;
    low-density rows are kept once. Nothing is dropped for lacking markers -- the
    project invariant is to rank, never gate.
  * VOCAB MIX CAP. data/seed/vocab_pairs.yaml is ~1.7x the density of marker-bearing
    human text, so it is capped at VOCAB_RATIO. Raising it tips the model into the
    self-parody failure eval.py detects. See that file's header for the arithmetic.
"""
import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCORED = ROOT / "data" / "processed" / "scored.jsonl"
VOCAB = ROOT / "data" / "seed" / "vocab_pairs.yaml"
OUT = ROOT / "data" / "processed"

# Calibrated against real data: at 30 this discarded 84% of rows, because Lowyat
# threads average well over a hundred posts. 120 trims only genuine megathreads.
MAX_ROWS_PER_THREAD = 120
HOLDOUT_FRAC = 0.02
VOCAB_RATIO = 0.10
MIN_PROMPT_TOKENS = 3
MIN_RESPONSE_TOKENS = 4
MAX_REPEAT = 3
PAIR_TARGET = 12000
SEED = 1337

sys.path.insert(0, str(Path(__file__).resolve().parent))
import markers


def capped(rows: list[dict]) -> list[dict]:
    """At most MAX_ROWS_PER_THREAD rows per thread, keeping the densest."""
    by_thread: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_thread[r["thread_uid"]].append(r)
    out, dropped = [], 0
    for rs in by_thread.values():
        if len(rs) <= MAX_ROWS_PER_THREAD:
            out += rs
        else:
            rs.sort(key=lambda r: -r["marker_score"])
            out += rs[:MAX_ROWS_PER_THREAD]
            dropped += len(rs) - MAX_ROWS_PER_THREAD
    print(f"  per-thread cap: kept {len(out)}, dropped {dropped} from oversized threads")
    return out


def weight(r: dict, median: float) -> int:
    """How many times a row appears in stage 1. Ranking, not gating."""
    if median <= 0:
        return 1
    return max(1, min(MAX_REPEAT, int(r["marker_score"] / median) if r["marker_score"] else 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    rng = random.Random(SEED)

    rows = [json.loads(l) for l in SCORED.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"[in] {len(rows)} scored rows")
    rows = capped(rows)

    rng.shuffle(rows)
    n_hold = max(int(len(rows) * HOLDOUT_FRAC), 1)
    holdout, train = rows[:n_hold], rows[n_hold:]
    train_uids = {r["uid"] for r in train}

    # ---- stage 1: flat text, marker-weighted ----
    dens = [r["marker_score"] for r in train if r["marker_score"] > 0]
    median = statistics.median(dens) if dens else 0.0
    stage1, tokens = [], 0
    for r in train:
        for _ in range(weight(r, median)):
            stage1.append({"text": r["text"]})
            tokens += r["n_tokens"]
    rng.shuffle(stage1)

    # ---- stage 2: real conversational pairs ----
    by_uid = {r["uid"]: r for r in train}
    pairs = []
    for r in train:
        p = by_uid.get(r["parent_uid"]) if r["parent_uid"] else None
        if p is None or p["uid"] not in train_uids:
            continue
        if p["n_tokens"] < MIN_PROMPT_TOKENS or r["n_tokens"] < MIN_RESPONSE_TOKENS:
            continue
        pairs.append({"prompt": p["text"], "response": r["text"],
                      "variety": r["variety"], "src": r["source"]})
    # Stage 2 is the BEHAVIOURAL stage, so response register matters more than volume.
    # Sorting alone achieved nothing (every pair was still emitted, so the set sat at
    # the corpus mean and measured 0.31x the human baseline -- undertrained). Partition
    # instead: every marker-bearing response is kept, then top up with the densest
    # remainder to reach PAIR_TARGET.
    for x in pairs:
        x["_d"] = markers.density(x["response"], x["variety"])
    withm = [x for x in pairs if x["_d"] > 0]
    rest = sorted((x for x in pairs if x["_d"] == 0), key=lambda x: -len(x["response"]))
    need = max(PAIR_TARGET - len(withm), 0)
    pairs = withm + rest[:need]
    print(f"  stage2 selection: {len(withm)} marker-bearing + {min(need, len(rest))} "
          f"topped up from {len(rest)} markerless")
    for x in pairs:
        x.pop("_d", None)

    # ---- vocab pairs, capped ----
    vocab = []
    if VOCAB.exists():
        vp = yaml.safe_load(VOCAB.read_text(encoding="utf-8"))["pairs"]
        want = int(len(pairs) * VOCAB_RATIO / max(1 - VOCAB_RATIO, 1e-9))
        reps = max(1, want // max(len(vp), 1))
        vocab = [{"prompt": x["prompt"], "response": x["response"],
                  "variety": "my", "src": "seed"} for x in vp for _ in range(reps)]
        vocab = vocab[:want]
    stage2 = pairs + vocab
    rng.shuffle(stage2)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("stage1", stage1), ("stage2", stage2), ("holdout", holdout)):
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[ok] stage1  {len(stage1):>7} rows  ~{tokens:,} tokens (weighted)")
    print(f"[ok] stage2  {len(stage2):>7} pairs ({len(pairs)} real + {len(vocab)} seed "
          f"= {len(vocab) / max(len(stage2), 1):.0%} seed)")
    print(f"[ok] holdout {len(holdout):>7} rows (never trained on)")

    if a.report:
        d2 = [markers.density(x["response"], x["variety"]) for x in stage2]
        hb = statistics.mean(r["marker_score"] for r in holdout if r["marker_count"]) \
            if any(r["marker_count"] for r in holdout) else 0
        print(f"\n  stage2 mean response density {statistics.mean(d2):.4f}")
        if hb:
            ratio = statistics.mean(d2) / hb
            # eval.py's band is 0.5x-1.6x. Checking only the upper bound printed "OK"
            # for a set measuring 0.26x, which is the undertrained failure, not success.
            if ratio < 0.5:
                verdict = "UNDERTRAINED -- too few markers; corpus is too sparse"
            elif ratio > 1.6:
                verdict = "SELF-PARODY RISK -- lower VOCAB_RATIO"
            else:
                verdict = "in band"
            print(f"  vs marker-bearing holdout    {hb:.4f}  = {ratio:.2f}x  {verdict}")
            withm = sum(1 for x in d2 if x > 0)
            print(f"  pairs whose response carries a marker: {withm}/{len(d2)} "
                  f"({withm / len(d2):.0%})")
        print(f"  stage2 by source: {dict(Counter(x['src'] for x in stage2))}")
        print(f"  varieties: {dict(Counter(x['variety'] for x in stage2))}")


if __name__ == "__main__":
    main()
