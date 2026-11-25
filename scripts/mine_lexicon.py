#!/usr/bin/env python3
"""Surface candidate dialect markers from the real corpus.

The seed lexicon is what could be written down a priori. This finds terms that are
frequent in the corpus but absent from a standard English dictionary -- which is
where the dialect actually lives. Output is a CANDIDATE list for human/agent review,
never auto-merged: the point is to catch markers nobody thought of, not to let typos
and usernames into the lexicon.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "processed" / "corpus.jsonl"
DICTS = [Path("/usr/share/dict/words"), Path("/usr/dict/words")]

sys.path.insert(0, str(Path(__file__).resolve().parent))
import markers


def english() -> set[str]:
    for d in DICTS:
        if d.exists():
            return {w.strip().lower() for w in d.read_text(errors="ignore").splitlines()}
    print("[warn] no system wordlist; candidates will be noisy", file=sys.stderr)
    return set()


def main() -> None:
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    eng, known = english(), {t.lower() for v in markers.lexicon().values() for t in v}

    counts: Counter[str] = Counter()
    docs: Counter[str] = Counter()
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        text = json.loads(line).get("text", "").lower()
        toks = re.findall(r"[a-z']{2,}", text)
        counts.update(toks)
        docs.update(set(toks))

    cands = [(w, n, docs[w]) for w, n in counts.most_common(4000)
             if w not in eng and w not in known and docs[w] >= 5 and not w.startswith("'")]

    print(f"{'term':<16}{'count':>8}{'docs':>7}")
    print("-" * 31)
    for w, n, d in cands[:top_n]:
        print(f"{w:<16}{n:>8}{d:>7}")
    print(f"\n{len(cands)} candidates. Review and add real markers to lexicon/markers.yaml.")


if __name__ == "__main__":
    main()
