#!/usr/bin/env python3
"""Pull posts + comments from Singlish/Manglish subreddits, preserving the comment tree.

The tree is the point. A comment's parent is a prompt and the comment is a response,
so parent_id turns this scrape into conversational training pairs for free -- and the
score tells us which responses are good. Flattening it loses that permanently.

Requires Reddit API credentials (free; run scripts/setup_reddit_creds.sh):
    REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT

Usage:
    python3 scrape_reddit.py                 # every enabled reddit source
    python3 scrape_reddit.py singapore       # named subreddits only

One-shot and resumable: output is append-only and completed submission ids are
logged to <sub>.seen, so an interrupted run is safe to re-run and never re-fetches
a thread it already finished.
"""
import json
import os
import sys
import time
from pathlib import Path

import praw
import prawcore

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import load

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "reddit"
POSTS_PER_SUB = 500
TIME_FILTER = "year"


def get_client() -> praw.Reddit:
    cid = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_CLIENT_SECRET")
    agent = os.environ.get("REDDIT_USER_AGENT")
    if not all([cid, secret, agent]):
        sys.exit(
            "Missing REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT.\n"
            "Run: scripts/setup_reddit_creds.sh"
        )
    return praw.Reddit(client_id=cid, client_secret=secret, user_agent=agent,
                       check_for_async=False)


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def bare(fullname: str | None) -> tuple[str | None, str | None]:
    """'t1_abc' -> ('abc', 'comment'). 't3_abc' -> ('abc', 'post')."""
    if not fullname or "_" not in fullname:
        return None, None
    prefix, _, ident = fullname.partition("_")
    return ident, {"t1": "comment", "t3": "post"}.get(prefix)


def scrape_sub(reddit: praw.Reddit, src: dict) -> None:
    sub_name = src["name"]
    out_file = OUT_DIR / f"{sub_name}.jsonl"
    seen_file = OUT_DIR / f"{sub_name}.seen"
    seen = load_seen(seen_file)

    tags = {"subreddit": sub_name, "variety": src["variety"], "register": src["register"]}
    written = skipped = 0

    # Append, never truncate. Opening with "w" here would silently destroy every
    # earlier run's data the moment this script was invoked a second time.
    with out_file.open("a", encoding="utf-8") as f, seen_file.open("a", encoding="utf-8") as sf:
        try:
            submissions = reddit.subreddit(sub_name).top(limit=POSTS_PER_SUB,
                                                         time_filter=TIME_FILTER)
            for submission in submissions:
                if submission.id in seen:
                    skipped += 1
                    continue

                batch = []
                text = f"{submission.title}\n{submission.selftext}".strip()
                if text:
                    batch.append({
                        "id": submission.id, "type": "post",
                        "parent_id": None, "parent_type": None,
                        "link_id": submission.id,
                        "text": text, "score": submission.score,
                        "created_utc": submission.created_utc, **tags,
                    })

                submission.comments.replace_more(limit=0)
                for c in submission.comments.list():
                    if not c.body or c.body in ("[deleted]", "[removed]"):
                        continue
                    pid, ptype = bare(getattr(c, "parent_id", None))
                    lid, _ = bare(getattr(c, "link_id", None))
                    batch.append({
                        "id": c.id, "type": "comment",
                        "parent_id": pid, "parent_type": ptype,
                        "link_id": lid or submission.id,
                        "text": c.body, "score": c.score,
                        "created_utc": c.created_utc, **tags,
                    })

                for rec in batch:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()

                # Only now is the thread complete. Logging it earlier would let an
                # interrupted run mark a half-written thread as finished.
                sf.write(submission.id + "\n")
                sf.flush()
                seen.add(submission.id)
                written += len(batch)

        except prawcore.exceptions.Redirect:
            print(f"[skip] r/{sub_name}: no such subreddit")
            return
        except prawcore.exceptions.Forbidden:
            print(f"[skip] r/{sub_name}: private or quarantined")
            return
        except KeyboardInterrupt:
            print(f"\n[interrupted] r/{sub_name}: {written} items written, safe to re-run")
            raise

    print(f"[ok] r/{sub_name} -> {out_file.name} (+{written} items, {skipped} threads already done)")


def main() -> None:
    wanted = sys.argv[1:]
    srcs = load(kind="reddit")
    if wanted:
        srcs = [s for s in srcs if s["name"] in wanted]
        missing = set(wanted) - {s["name"] for s in srcs}
        if missing:
            sys.exit(f"Not in sources.yaml: {', '.join(sorted(missing))}")
    if not srcs:
        sys.exit("No enabled reddit sources in sources.yaml")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reddit = get_client()
    for i, src in enumerate(srcs):
        scrape_sub(reddit, src)
        if i + 1 < len(srcs):
            time.sleep(2)


if __name__ == "__main__":
    main()
