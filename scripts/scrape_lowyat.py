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
import markers
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


def discover_boards(f: Fetcher, boards: list[str], limit: int,
                    page_step: int = 30, max_pages: int = 60) -> list[tuple[str, str]]:
    """(thread_id, board) by crawling named board listing pages.

    Replaces sitemap discovery. The sitemap spans all 115 boards and the tech and
    trading boards dominate it by volume while scoring 0.0000 marker density, so
    recency-based discovery spends most of the budget on plain English about graphics
    cards. Board paths like /Kopitiam are allowed by robots.txt (only /index.php,
    /lofiversion and one topic are disallowed) and paginate as /Board/+30.
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    per_board = max(limit // max(len(boards), 1), 1)

    for board in boards:
        got = 0
        for page in range(max_pages):
            url = f"{BASE}/{board}" if page == 0 else f"{BASE}/{board}/+{page * page_step}"
            html = f.get(url)
            if not html:
                break
            # dict.fromkeys dedupes within the page while preserving order; board
            # pages link the same topic up to 8 times.
            ids = list(dict.fromkeys(re.findall(r"/topic/(\d+)", html)))
            fresh = []
            for i in ids:
                if i not in seen:
                    seen.add(i)
                    fresh.append(i)
                    found.append((i, board))
            got += len(fresh)
            if got >= per_board or not fresh:
                break
        print(f"  {board}: {got} threads")
        if len(found) >= limit:
            break
    return found[:limit]


def discover(f: Fetcher, limit: int) -> list[str]:
    """Thread ids from the sitemap. Kept as a fallback; prefer discover_boards."""
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


def board_of(soup) -> str | None:
    """Board name from the navstrip ('Lowyat.NET -> Kopitiam').

    Recorded per thread because the sitemap exposes only /topic/<id> with no board,
    so without this the saturation report cannot tell which boards are actually
    Manglish-dense -- and recency-based discovery skews heavily to the hardware and
    trading boards, which are written in fairly plain English.
    """
    nav = soup.select_one("#navstrip, .navstrip")
    if not nav:
        return None
    parts = [p.strip() for p in nav.get_text(">", strip=True).split(">") if p.strip()]
    return parts[-1] if parts else None


def parse_thread(html: str, thread_id: str, tags: dict) -> list[dict]:
    s = BeautifulSoup(html, "lxml")
    board = board_of(s)
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
                    "board": board, "text": p["text"], **tags})
    return out


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--topic", action="append", default=[])
    ap.add_argument("--floor", type=float, default=None,
                    help="min mean marker density for a thread to be kept")
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

    floor = args.floor if args.floor is not None else src.get("min_thread_density", 0.0)
    f = Fetcher()

    if args.topic:
        pairs = [(t, None) for t in args.topic]
    elif src.get("discover") == "boards" and src.get("boards"):
        print(f"discovering across {len(src['boards'])} boards:")
        pairs = discover_boards(f, src["boards"], limit + len(seen))
    else:
        pairs = [(t, None) for t in discover(f, limit + len(seen))]

    todo = [(t, b) for t, b in pairs if t not in seen][:limit]
    print(f"{len(pairs)} discovered, {len(seen)} already done, {len(todo)} to fetch "
          f"(density floor {floor})")

    skip_file = OUT_DIR / "lowyat.skipped"
    posts = threads = skipped_thin = 0
    with out_file.open("a", encoding="utf-8") as fh, \
         seen_file.open("a", encoding="utf-8") as sf, \
         skip_file.open("a", encoding="utf-8") as kf:
        try:
            for tid, board in todo:
                if tid in seen:      # guard: discovery must never cause a re-fetch
                    continue
                seen.add(tid)
                html = f.get(f"{BASE}/topic/{tid}/all")
                if html is None:
                    continue
                rows = parse_thread(html, tid, tags)
                if not rows:
                    sf.write(tid + "\n"); sf.flush()
                    continue

                # Thread-level density gate. Cheaper than filtering later, and it stops
                # zero-dialect megathreads from dominating the corpus by sheer volume --
                # the largest threads measured exactly 0.0000. Gating THREADS, not
                # utterances: the project invariant is to rank individual text, never
                # gate it, and a thread is cheap to re-fetch if the floor was wrong.
                dens = [markers.density(r["text"], tags["variety"]) for r in rows]
                mean = sum(dens) / len(dens)
                if mean < floor:
                    kf.write(json.dumps({"thread_id": tid, "board": board or rows[0].get("board"),
                                         "posts": len(rows), "mean_density": round(mean, 5)}) + "\n")
                    kf.flush()
                    sf.write(tid + "\n"); sf.flush()
                    skipped_thin += 1
                    continue

                for r in rows:
                    if board and not r.get("board"):
                        r["board"] = board
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                fh.flush()
                sf.write(tid + "\n"); sf.flush()
                posts += len(rows)
                threads += 1
                if threads % 25 == 0:
                    print(f"  kept {threads} threads / {posts} posts, "
                          f"skipped {skipped_thin} below floor")
        except KeyboardInterrupt:
            print(f"\n[interrupted] {threads} threads written, safe to re-run")

    print(f"[ok] lowyat -> {out_file.name} (+{threads} threads, {posts} posts, "
          f"{skipped_thin} threads below density floor)")


if __name__ == "__main__":
    main()
