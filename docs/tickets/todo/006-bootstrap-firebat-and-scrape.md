# 006 — Bootstrap firebat and run the one-shot scrapes

**Phase:** P0 · **Depends-on:** 001, 002, 003, 004, 005 · **Gate:** none

## Goal
Get the corpus onto firebat: venv, directory layout, secrets, then run each scraper once.

## Why
firebat is the data plane — 409 GB free, always on, and not carrying the Mac's 58 GB ceiling.
This is the ticket where the corpus actually comes into existence.

**No cron, no CronJob, no timer.** Scrapers are deliberate one-shot runs, triggered when a
source is added. They are resumable (001/004/005) so an interrupted pass is safe to continue.

## Scope
- On firebat: clone the repo, `python3 -m venv`, install `requirements.txt`.
- Corpus root at `/var/lib/lalalm/data/` (not inside the git checkout — the repo's `data/` is
  gitignored and the corpus should not sit where a stray `git clean` can reach it). Symlink
  `data/` in the checkout to it.
- Secrets: `/etc/lalalm/env` owned root, mode 600, sourced by the run script.
- `scripts/run_scrapes.sh` — runs every enabled source in `sources.yaml` once, logs to
  `/var/log/lalalm/`, exits non-zero if any source fails, safe to re-run.
- Run it. Expect hours. It will get interrupted; re-run until each source reports complete.

## Done-when
```sh
ssh firebat 'set -e; test -d /var/lib/lalalm/data/raw; \
  for d in reddit youtube forums; do \
    n=$(find /var/lib/lalalm/data/raw/$d -name "*.jsonl" | wc -l); \
    echo "$d: $n files"; test "$n" -gt 0; \
  done; echo ok'
```

## Files
`scripts/run_scrapes.sh`, firebat filesystem

## Notes
Keep an eye on firebat's RAM during scraping — it has ~11 GB available and is carrying k3s
workloads. The scrapers should stream to disk, never accumulate a corpus in memory.
