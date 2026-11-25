# 001 — Reddit scraper: preserve comment tree, make resumable

**Phase:** P0 · **Depends-on:** — · **Gate:** none

## Goal
Rewrite `scripts/scrape_reddit.py` so each record carries the fields needed to reconstruct the
comment tree, and so an interrupted run is safe to re-run.

## Why
A model that *talks* Singlish needs prompt→response pairs. Reddit hands you millions for free:
a comment's parent is the prompt, the comment is the response, the score says which responses
are good. The current scraper writes `{id, type, text, score}` and discards the links
permanently — flattening the most valuable structure in the data into an unordered bag of text.

Separately, the current `open("w")` **truncates the output file on every run**, so a second
scrape silently destroys the first.

## Scope
- Add `parent_id`, `link_id`, `created_utc`, `subreddit` to every record.
- Add `variety` and `register` from the source config (see 002); until 002 lands, accept them
  as CLI args.
- Output `open("a")` append-mode, not `"w"`.
- Maintain `data/raw/reddit/<sub>.seen` — one submission ID per line, appended **after** that
  submission's comments are fully written. On start, read it and skip those IDs.
- Flush per submission so a kill mid-run loses at most one thread.

## Done-when
```sh
python3 -c "import ast,sys; src=open('scripts/scrape_reddit.py').read(); \
assert 'parent_id' in src and 'created_utc' in src and '.seen' in src; \
assert 'open(\"w\"' not in src and \"open('w'\" not in src; \
ast.parse(src); print('ok')"
```
Plus: run it against one small subreddit, kill it mid-run, re-run, and confirm the output JSONL
grows rather than restarting and that no submission ID appears twice.

## Files
`scripts/scrape_reddit.py`

## Notes
`replace_more(limit=0)` drops deep comment chains. That is an acceptable trade for now — it
avoids a large number of extra API calls — but record it as a known corpus limitation in 008's
saturation report, because it biases the pair set toward top-level replies.
