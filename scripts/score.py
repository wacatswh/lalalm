#!/usr/bin/env python3
"""Score corpus items by dialect-marker density; dedup exactly.

Two deliberate non-decisions, both project invariants:

  * No language-ID gate. langid/fastText label Singlish as either "English" or
    low-confidence garbage, so a language filter deletes precisely the best text
    here. marker_score RANKS and WEIGHTS; it never gates.
  * Exact-hash dedup only, never near-duplicate. Short lah-heavy replies look
    near-identical to MinHash, which would delete the strongest register signal
    in the corpus.

The only thing dropped is text too short to be language at all.
"""
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN = ROOT / "data" / "processed" / "corpus.jsonl"
OUT = ROOT / "data" / "processed" / "scored.jsonl"
MIN_TOKENS = 3

sys.path.insert(0, str(Path(__file__).resolve().parent))
import markers


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def main() -> None:
    rows = [json.loads(l) for l in IN.read_text(encoding="utf-8").splitlines() if l.strip()]

    seen: set[str] = set()
    out, dropped_short, dropped_dup = [], 0, 0
    for r in rows:
        toks = markers.tokens(r["text"])
        if len(toks) < MIN_TOKENS:
            dropped_short += 1
            continue
        h = hashlib.sha1(norm(r["text"]).encode()).hexdigest()
        if h in seen:
            dropped_dup += 1
            continue
        seen.add(h)

        hits = markers.hits(r["text"], r["variety"])
        r["marker_hits"] = hits
        r["marker_count"] = len(hits)
        r["marker_score"] = round(len(hits) / len(toks), 5)
        r["n_tokens"] = len(toks)
        out.append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"[ok] {len(out)} rows -> {OUT.relative_to(ROOT)}")
    print(f"  dropped: {dropped_short} too short (<{MIN_TOKENS} tokens), "
          f"{dropped_dup} exact duplicates")
    for v in ("sg", "my"):
        rs = [r for r in out if r["variety"] == v]
        if not rs:
            print(f"  {v}: no data")
            continue
        with_m = sum(1 for r in rs if r["marker_count"])
        mean = sum(r["marker_score"] for r in rs) / len(rs)
        print(f"  {v}: {len(rs)} rows, mean marker_score {mean:.4f}, "
              f"{with_m} ({with_m / len(rs):.0%}) contain >=1 marker")
    top = Counter(m for r in out for m in r["marker_hits"]).most_common(12)
    print(f"  top markers: {', '.join(f'{m}({n})' for m, n in top)}")


if __name__ == "__main__":
    main()
