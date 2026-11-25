#!/usr/bin/env python3
"""Fold all raw sources into one normalized schema, scrubbing PII at the boundary.

Three scrapers produce three shapes. Everything downstream -- scoring, dedup, pair
building, saturation -- reads the one schema below, and because the scrub happens
here no later stage ever sees a raw identifier.

    {uid, source, source_id, parent_uid, thread_uid, text, score, created,
     variety, register}

uid is derived from source + source_id, so re-ingesting is idempotent.
parent_uid is null for roots and is what stage 2's conversational pairs are built
from -- it only exists because the scrapers bothered to preserve the tree.

Usage:
    python3 ingest.py            # write data/processed/corpus.jsonl
    python3 ingest.py --check    # same, then assert the invariants
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "corpus.jsonl"

# ---------------------------------------------------------------- PII
# Order matters: identifiers that contain digits-and-dashes are scrubbed before
# the looser phone patterns, or a phone rule eats half an NRIC and leaves the rest.
SCRUBS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b\d{6}-\d{2}-\d{4}\b"), "<nric>"),                  # MY NRIC
    (re.compile(r"\b[STFGM]\d{7}[A-Z]\b"), "<nric>"),                  # SG NRIC/FIN
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<email>"),
    (re.compile(r"https?://\S+|\bwww\.\S+"), "<url>"),                 # kept as a token:
                                                                       # link presence is
                                                                       # register signal
    (re.compile(r"\b01\d[-\s]?\d{3,4}[-\s]?\d{4}\b"), "<phone>"),      # MY mobile
    (re.compile(r"(?<!\d)(?:\+?6)?0\d{1,2}[-\s]\d{6,8}(?!\d)"), "<phone>"),  # MY landline
    (re.compile(r"(?<![\d.])[89]\d{7}(?![\d.])"), "<phone>"),          # SG 8-digit
    (re.compile(r"(?:^|(?<=\s))/?u/[A-Za-z0-9_-]{3,20}\b"), "<user>"),  # reddit handles
    (re.compile(r"(?:^|(?<=\s))@[A-Za-z0-9_.]{2,30}\b"), "<user>"),
]


# Forum chrome that is not language. "This post has been edited by <user> : <date>"
# appeared in 431 of the first 4037 rows -- boilerplate AND a username leak in a form
# the handle patterns above do not match.
BOILERPLATE: list[re.Pattern] = [
    re.compile(r"This post has been edited by\s+[^:]{1,40}:\s*[A-Za-z0-9 ,:]{0,30}(?:[AP]M)?",
               re.I),
    re.compile(r"Attached image\(s\)|Attached thumbnail\(s\)|Click to enlarge", re.I),
    re.compile(r"\bQUOTE\s*\([^)]{0,80}\)", re.I),  # quote blocks the selectors missed
]


def strip_boilerplate(text: str) -> str:
    for pat in BOILERPLATE:
        text = pat.sub(" ", text)
    return text


def scrub(text: str) -> str:
    text = strip_boilerplate(text)
    for pat, repl in SCRUBS:
        text = pat.sub(repl, text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- readers
def jsonl(path: Path):
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def from_reddit(r: dict) -> dict:
    return {
        "uid": f"reddit:{r['id']}", "source": "reddit", "source_id": r["id"],
        "parent_uid": f"reddit:{r['parent_id']}" if r.get("parent_id") else None,
        "thread_uid": f"reddit:{r.get('link_id') or r['id']}",
        "text": scrub(r.get("text", "")), "score": r.get("score"),
        "created": r.get("created_utc"),
        "variety": r["variety"], "register": r["register"],
    }


def from_lowyat(r: dict) -> dict:
    return {
        "uid": f"lowyat:{r['post_id']}", "source": "lowyat", "source_id": r["post_id"],
        "parent_uid": f"lowyat:{r['parent_post_id']}" if r.get("parent_post_id") else None,
        "thread_uid": f"lowyat:{r['thread_id']}",
        "text": scrub(r.get("text", "")), "score": None, "created": r.get("created"),
        "board": r.get("board"),
        "variety": r["variety"], "register": r["register"],
    }


def from_youtube(rows: list[dict]) -> list[dict]:
    """Captions have no reply tree, so adjacency is the only available structure:
    each cue's parent is the previous cue in the same video. Weaker than a real
    reply edge -- much of it is monologue -- so 009 should weight these below
    forum/reddit pairs rather than treat them as equivalent."""
    out, prev_by_video = [], {}
    for r in sorted(rows, key=lambda x: (x.get("video_id", ""), x.get("start", 0))):
        vid, start = r.get("video_id"), r.get("start", 0)
        if not vid:
            continue
        uid = f"youtube:{vid}:{start}"
        out.append({
            "uid": uid, "source": "youtube", "source_id": f"{vid}:{start}",
            "parent_uid": prev_by_video.get(vid), "thread_uid": f"youtube:{vid}",
            "text": scrub(r.get("text", "")), "score": None, "created": start,
            "variety": r["variety"], "register": r["register"],
        })
        prev_by_video[vid] = uid
    return out


def collect() -> list[dict]:
    rows: list[dict] = []
    for p in sorted((RAW / "reddit").glob("*.jsonl")):
        rows += [from_reddit(r) for r in jsonl(p)]
    for p in sorted((RAW / "forums").glob("*.jsonl")):
        rows += [from_lowyat(r) for r in jsonl(p)]
    yt = [r for p in sorted((RAW / "youtube").glob("*.jsonl")) for r in jsonl(p)]
    if yt:
        rows += from_youtube(yt)

    rows = [r for r in rows if r["text"]]
    # Last writer wins: re-ingest of an updated scrape replaces, never duplicates.
    by_uid = {r["uid"]: r for r in rows}
    out = list(by_uid.values())

    # A parent that was never ingested (deleted comment, trimmed thread) must not
    # leave a dangling edge, or 009 silently builds pairs against missing text.
    known = set(by_uid)
    dangling = 0
    for r in out:
        if r["parent_uid"] and r["parent_uid"] not in known:
            r["parent_uid"] = None
            dangling += 1
    if dangling:
        print(f"  cleared {dangling} dangling parent edges (parent not in corpus)")
    return out


def check(rows: list[dict]) -> None:
    assert rows, "empty corpus"
    need = {"uid", "source", "source_id", "parent_uid", "thread_uid", "text",
            "variety", "register"}
    assert all(need <= set(r) for r in rows), "schema mismatch"
    assert len({r["uid"] for r in rows}) == len(rows), "uid not unique"
    assert all(r["variety"] in ("sg", "my") for r in rows), "bad variety"
    known = {r["uid"] for r in rows}
    assert all(r["parent_uid"] in known for r in rows if r["parent_uid"]), "dangling parent"
    leak = re.compile(r"\d{6}-\d{2}-\d{4}|\b[STFGM]\d{7}[A-Z]\b|[\w.+-]+@[\w-]+\.[\w.]+")
    bad = [r["uid"] for r in rows if leak.search(r["text"])]
    assert not bad, f"PII leaked in {len(bad)} rows, e.g. {bad[:3]}"
    print("  checks passed")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    rows = collect()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    from collections import Counter
    print(f"[ok] {len(rows)} rows -> {OUT.relative_to(ROOT)}")
    print(f"  by source:  {dict(Counter(r['source'] for r in rows))}")
    print(f"  by variety: {dict(Counter(r['variety'] for r in rows))}")
    print(f"  with parent: {sum(1 for r in rows if r['parent_uid'])}")
    if a.check:
        check(rows)


if __name__ == "__main__":
    sys.exit(main())
