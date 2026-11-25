"""Prove 001: append-mode + .seen means an interrupted run resumes, never duplicates."""
import json, sys, types, shutil
from pathlib import Path
sys.path.insert(0, "scripts")
import scrape_reddit as sr

TMP = Path("/tmp/lalalm-test-out")
shutil.rmtree(TMP, ignore_errors=True); TMP.mkdir(parents=True)
sr.OUT_DIR = TMP

class C:
    def __init__(s, i, p, l): s.id, s.parent_id, s.link_id, s.body, s.score, s.created_utc = i, p, l, f"body {i} lah", 5, 1.0
class Cs:
    def __init__(s, c): s._c = c
    def replace_more(s, limit=0): pass
    def list(s): return s._c
class S:
    def __init__(s, i, n):
        s.id, s.title, s.selftext, s.score, s.created_utc = i, f"title {i}", "selftext", 10, 1.0
        s.comments = Cs([C(f"{i}c{k}", f"t3_{i}" if k == 0 else f"t1_{i}c0", f"t3_{i}") for k in range(n)])
class Sub:
    def __init__(s, subs): s._s = subs
    def top(s, limit, time_filter): return iter(s._s)
class R:
    def __init__(s, subs): s._s = subs
    def subreddit(s, name): return Sub(s._s)

src = {"name": "testsub", "variety": "my", "register": "social"}

# Run 1: two threads
sr.scrape_sub(R([S("t1", 2), S("t2", 2)]), src)
after1 = (TMP / "testsub.jsonl").read_text().strip().splitlines()

# Run 2: same two threads PLUS a new one. Must skip the first two, append only the new.
sr.scrape_sub(R([S("t1", 2), S("t2", 2), S("t3", 2)]), src)
after2 = (TMP / "testsub.jsonl").read_text().strip().splitlines()

rows = [json.loads(l) for l in after2]
ids = [r["id"] for r in rows]
seen = (TMP / "testsub.seen").read_text().split()

assert len(after2) > len(after1), "output shrank -- truncation bug is back"
assert after2[:len(after1)] == after1, "run 1 data was altered"
assert len(ids) == len(set(ids)), f"duplicate records: {ids}"
assert seen == ["t1", "t2", "t3"], seen
tree = {r["id"]: (r["parent_id"], r["parent_type"]) for r in rows}
assert tree["t3c0"] == ("t3", "post"), tree["t3c0"]
assert tree["t3c1"] == ("t3c0", "comment"), tree["t3c1"]
assert all(r["variety"] == "my" for r in rows)
print(f"PASS: run1={len(after1)} rows -> run2={len(after2)} rows, no dupes, tree intact, seen={seen}")
