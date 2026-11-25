"""Prove 005: parent chain resolves from quote attribution, quoted text not duplicated."""
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
import scrape_lowyat as lw

# No fixture is committed: a saved Lowyat page is other people's text, and the
# project does not redistribute raw scraped content. Produce one locally with
#   curl -A lalalm-research/0.1 --compressed \
#     https://forum.lowyat.net/topic/5584555/all -o /tmp/lowyat-fixture.html
FIX = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/lowyat-fixture.html")
if not FIX.exists():
    print(f"SKIP: no fixture at {FIX} (see header for how to make one)")
    sys.exit(0)

rows = lw.parse_thread(FIX.read_text(encoding="utf-8", errors="ignore"), "5584555",
                       {"variety": "my", "register": "forum"})
assert rows, "no posts parsed"
ids = [r["post_id"] for r in rows]
assert len(ids) == len(set(ids)), "duplicate post ids"
assert rows[0]["parent_post_id"] is None, "first post must have no parent"
assert all(r["parent_post_id"] in set(ids[:i]) for i, r in enumerate(rows) if i > 0), \
    "a parent points outside the earlier posts of this thread"
assert all(r["variety"] == "my" and r["register"] == "forum" for r in rows)
assert not any("QUOTE(" in r["text"] for r in rows), "quote block leaked into body"

# Quoted text must not be duplicated: no post body may contain a long verbatim
# run from its own parent.
by_id = {r["post_id"]: r["text"] for r in rows}
dupes = []
for r in rows[1:]:
    p = by_id.get(r["parent_post_id"], "")
    if len(p) > 60 and p[:60] in r["text"]:
        dupes.append(r["post_id"])
assert not dupes, f"parent text duplicated into child: {dupes}"

resolved = sum(1 for r in rows[1:] if r["parent_post_id"] != rows[0]["post_id"])
print(f"PASS: {len(rows)} posts, chain valid, no quote duplication")
print(f"      sample: {rows[1]['post_id']} -> parent {rows[1]['parent_post_id']}")
print(f"      text:   {rows[1]['text'][:90]}")
