# 005 — Lowyat.NET forum scraper

**Phase:** P0 · **Depends-on:** 002 · **Gate:** none

## Goal
A resumable one-shot scraper for Lowyat.NET forum threads, output matching the shared record
schema.

## Why
This is the ticket that decides whether Manglish is real in this corpus or a rounding error.
`r/malaysia` is substantially more formal-English than `r/singapore`, so equal treatment of the
two subreddits still yields a Singlish-skewed corpus. Lowyat is Manglish-dense, long-running,
and plain HTML — which is why `beautifulsoup4` is already in `requirements.txt` and
`data/raw/forums/` already exists and is empty.

Forum threads also give the same parent→reply structure Reddit does, including quoted-reply
blocks that make the pair explicit.

## Scope
- `scripts/scrape_lowyat.py`, boards read from `sources.yaml`.
- Per post: `{thread_id, post_id, parent_post_id, created, text, variety: my, register: forum}`.
  Derive `parent_post_id` from quote blocks where present; else the preceding post in-thread.
- **Strip quoted text out of the reply body** after using it to establish the parent link —
  otherwise the parent's words are duplicated into the child and inflate the corpus.
- `.seen` log of completed thread IDs, append-mode output, flush per thread.
- Be polite: a real `User-Agent` identifying the project, ≥1s between requests, honour
  `robots.txt`, back off on 429/5xx. Resumability exists precisely so a restart does not
  re-hammer the site.

## Done-when
```sh
python3 -c "import ast; src=open('scripts/scrape_lowyat.py').read(); \
assert 'parent_post_id' in src and '.seen' in src and 'robots' in src.lower(); \
ast.parse(src); print('ok')"
```
Plus: scrape one thread, confirm the reconstructed parent chain matches the thread as rendered
in a browser, and confirm quoted text does not appear twice.

## Files
`scripts/scrape_lowyat.py`, `sources.yaml`

## Notes
Check `robots.txt` before writing the selectors. If Lowyat disallows the board paths, stop and
move this to `blocked/` with a note rather than proceeding — and bring the alternative Manglish
sources (Malaysian YouTube, more Malaysian subreddits) forward to compensate.
