#!/usr/bin/env python3
"""Scrape Lowyat.NET forum threads. This is the Manglish depth source.

Why this file exists: r/malaysia is noticeably more formal-English than
r/singapore, so treating the two subreddits as equivalent still yields a
Singlish-skewed corpus. Lowyat is Manglish-dense and plain HTML.

Politeness, in order of importance:
  * robots.txt is parsed and enforced per URL. For User-agent:* it disallows
    /index.php and /lofiversion, so ONLY /topic/<id> URLs are used -- never the
    legacy index.php?showtopic= form. It also disallows one specific huge topic,
    which robotparser handles for us.
  * One request per THREAD via /topic/<id>/all, not one per page.
  * >=1.5s between requests, identifying User-Agent, backoff on 429/5xx.
  * Resumable, so an interrupted run never re-walks the site from the start.

Authors are used to resolve quote->parent links and are then discarded; no
username is ever written to disk.

Usage:
    python3 scrape_lowyat.py                  # sitemap discovery
    python3 scrape_lowyat.py --max 200        # cap threads this run
    python3 scrape_lowyat.py --topic 5584555  # one thread
"""
import argparse
import json
import re
import sys
import time
import urllib.robotparser
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import load

BASE = "https://forum.lowyat.net"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "forums"
UA = "lalalm-research/0.1 (Singlish/Manglish corpus research; +github.com/wacatswh/lalalm)"
DELAY = 1.5
MAX_THREADS_DEFAULT = 2000
QUOTE_RE = re.compile(r"QUOTE\s*\(\s*(?P<author>[^@)]+?)\s*@\s*(?P<when>[^)]+?)\s*\)", re.I)
TIME_RE = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)", re.I)


class Fetcher:
    """Single session, robots-aware, rate-limited, backs off on transient errors."""

    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.last = 0.0
        self.rp = urllib.robotparser.RobotFileParser()
        self.rp.set_url(f"{BASE}/robots.txt")
        try:
            self.rp.read()
        except Exception as e:
            sys.exit(f"Cannot read robots.txt ({e}). Refusing to scrape blind.")

    def allowed(self, url: str) -> bool:
        return self.rp.can_fetch("*", url)

    def get(self, url: str, tries: int = 4) -> str | None:
        if not self.allowed(url):
            print(f"[robots] disallowed, skipping: {url}")
            return None
        for attempt in range(tries):
            wait = DELAY - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            try:
                r = self.s.get(url, timeout=30)
            except requests.RequestException as e:
                print(f"[retry {attempt + 1}] {url}: {e}")
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 200:
                return r.text
            if r.status_code in (429, 500, 502, 503, 504):
                back = 2 ** attempt * 5
                print(f"[backoff {back}s] HTTP {r.status_code} {url}")
                time.sleep(back)
                continue
            print(f"[skip] HTTP {r.status_code} {url}")
            return None
        return None


def discover(f: Fetcher, limit: int) -> list[str]:
    """Thread ids from the sitemap. Never guesses board ids."""
    index = f.get(f"{BASE}/sitemap_index.xml")
    if not index:
        return []
    maps = re.findall(r"<loc>([^<]*sitemap-(?:recent|topics-\d+)\.xml[^<]*)</loc>", index)
    # Recent first: freshest language, and a sane place to stop.
    maps.sort(key=lambda u: ("recent" not in u, u))

    ids: list[str] = []
    for m in maps:
        body = f.get(m)
        if not body:
            continue
        ids += re.findall(r"<loc>https?://forum\.lowyat\.net/topic/(\d+)", body)
        if len(ids) >= limit:
            break
    seen: set[str] = set()
    return [i for i in ids if not (i in seen or seen.add(i))][:limit]


def post_time(tbl) -> str:
    d = tbl.select_one(".postdetails")
    return d.get_text(" ", strip=True) if d else ""


def post_author(tbl) -> str:
    a = tbl.select_one('a[href^="/user/"]')
    return a.get_text(strip=True) if a else ""


def parse_thread(html: str, thread_id: str, tags: dict) -> list[dict]:
    s = BeautifulSoup(html, "lxml")
    raw: list[dict] = []

    for tbl in s.select("table.post_table"):
        pid = (tbl.get("id") or "").replace("post_", "")
        body = tbl.select_one("div.postcolor")
        if not pid or body is None:
            continue

        # Pull quote attribution BEFORE removing the blocks, then drop the quoted
        # text -- leaving it in would duplicate the parent's words into the child
        # and inflate the corpus with its own content.
        quoted_author = quoted_when = None
        qt = body.select_one("div.quotetop")
        if qt:
            m = QUOTE_RE.search(qt.get_text(" ", strip=True))
            if m:
                quoted_author = m.group("author").strip()
                quoted_when = m.group("when").strip()
        for q in body.select("div.quotetop, div.quotemain"):
            q.decompose()

        text = re.sub(r"\s+", " ", body.get_text(" ", strip=True)).strip()
        if not text:
            continue
        raw.append({"post_id": pid, "author": post_author(tbl), "when": post_time(tbl),
                    "qa": quoted_author, "qw": quoted_when, "text": text})

    # Signatures live in post_table but outside div.postcolor, so they are already
    # excluded by the selector above -- verified against live markup.

    out: list[dict] = []
    for i, p in enumerate(raw):
        parent = None
        if p["qa"]:
            want_time = TIME_RE.search(p["qw"] or "")
            want_time = want_time.group(1).upper().replace(" ", "") if want_time else None
            for earlier in reversed(raw[:i]):
                if earlier["author"].lower() != p["qa"].lower():
                    continue
                if want_time:
                    got = TIME_RE.search(earlier["when"] or "")
                    if not got or got.group(1).upper().replace(" ", "") != want_time:
                        continue
                parent = earlier["post_id"]
                break
        if parent is None and i > 0:
            parent = raw[i - 1]["post_id"]  # fallback: preceding post in-thread

        out.append({"thread_id": thread_id, "post_id": p["post_id"],
                    "parent_post_id": parent, "created": p["when"],
                    "text": p["text"], **tags})
    return out


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--topic", action="append", default=[])
    args = ap.parse_args()

    srcs = load(kind="lowyat")
    if not srcs:
        sys.exit("No enabled lowyat source in sources.yaml")
    src = srcs[0]
    tags = {"variety": src["variety"], "register": src["register"]}
    limit = args.max or src.get("max_threads", MAX_THREADS_DEFAULT)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file, seen_file = OUT_DIR / "lowyat.jsonl", OUT_DIR / "lowyat.seen"
    seen = load_seen(seen_file)

    f = Fetcher()
    ids = args.topic or discover(f, limit + len(seen))
    todo = [i for i in ids if i not in seen][:limit]
    print(f"{len(ids)} discovered, {len(seen)} already done, {len(todo)} to fetch")

    posts = threads = 0
    with out_file.open("a", encoding="utf-8") as fh, seen_file.open("a", encoding="utf-8") as sf:
        try:
            for tid in todo:
                html = f.get(f"{BASE}/topic/{tid}/all")
                if html is None:
                    continue
                rows = parse_thread(html, tid, tags)
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                fh.flush()
                sf.write(tid + "\n")
                sf.flush()
                posts += len(rows)
                threads += 1
                if threads % 25 == 0:
                    print(f"  {threads} threads, {posts} posts")
        except KeyboardInterrupt:
            print(f"\n[interrupted] {threads} threads written, safe to re-run")

    print(f"[ok] lowyat -> {out_file.name} (+{threads} threads, {posts} posts)")


if __name__ == "__main__":
    main()
