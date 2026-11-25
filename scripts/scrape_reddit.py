#!/usr/bin/env python3
"""Pull posts + comments from Singlish/Manglish-heavy subreddits via PRAW.

Requires Reddit API credentials (free, from https://www.reddit.com/prefs/apps
-> create app -> type "script"). Set these env vars before running:
    REDDIT_CLIENT_ID
    REDDIT_CLIENT_SECRET
    REDDIT_USER_AGENT   (e.g. "lalalm-scraper/0.1 by u/yourusername")

Usage:
    python3 scrape_reddit.py singapore malaysia hardwarezone
    (subreddit names, space separated; defaults to a built-in list if omitted)

Output: data/raw/reddit/<subreddit>.jsonl  (one JSON object per line:
        {"id", "type": "post"|"comment", "text", "score"})
"""
import json
import os
import sys
from pathlib import Path

import praw

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "reddit"
DEFAULT_SUBS = ["singapore", "malaysia", "SingaporeRaw", "asianamerican"]
POSTS_PER_SUB = 500


def get_client() -> praw.Reddit:
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT")
    if not all([client_id, client_secret, user_agent]):
        print("Missing REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT env vars.")
        print("Get free credentials at https://www.reddit.com/prefs/apps (create a 'script' app).")
        sys.exit(1)
    return praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)


def scrape_sub(reddit: praw.Reddit, sub_name: str) -> None:
    out_file = OUT_DIR / f"{sub_name}.jsonl"
    count = 0
    with out_file.open("w", encoding="utf-8") as f:
        for submission in reddit.subreddit(sub_name).top(limit=POSTS_PER_SUB, time_filter="year"):
            text = f"{submission.title}\n{submission.selftext}".strip()
            if text:
                f.write(json.dumps({"id": submission.id, "type": "post", "text": text, "score": submission.score}) + "\n")
                count += 1
            submission.comments.replace_more(limit=0)
            for comment in submission.comments.list():
                if comment.body and comment.body not in ("[deleted]", "[removed]"):
                    f.write(json.dumps({"id": comment.id, "type": "comment", "text": comment.body, "score": comment.score}) + "\n")
                    count += 1
    print(f"[ok] r/{sub_name} -> {out_file.name} ({count} items)")


def main():
    subs = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_SUBS
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reddit = get_client()
    for sub in subs:
        try:
            scrape_sub(reddit, sub)
        except Exception as e:
            print(f"[error] r/{sub}: {e}")


if __name__ == "__main__":
    main()
