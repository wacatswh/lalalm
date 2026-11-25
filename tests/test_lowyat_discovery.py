"""Prove the discovery dedup fix: board pages link the same topic many times."""
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
import scrape_lowyat as lw

# A board page links each topic repeatedly (title, last-post, reply links).
PAGE = ('<a href="/topic/111">t</a><a href="/topic/111">last</a><a href="/topic/111">x</a>'
        '<a href="/topic/222">t</a><a href="/topic/222">last</a>')

class FakeFetcher:
    def __init__(s): s.calls = []
    def get(s, url):
        s.calls.append(url)
        return PAGE if "/Board" in url else None

f = FakeFetcher()
found = lw.discover_boards(f, ["Board"], limit=50)
ids = [t for t, _ in found]
assert ids == ["111", "222"], f"expected deduped ['111','222'], got {ids}"
assert len(ids) == len(set(ids)), "duplicates survived discovery"
assert all(b == "Board" for _, b in found), "board tag lost"
print(f"PASS: 5 links -> {len(ids)} unique threads {ids}")
