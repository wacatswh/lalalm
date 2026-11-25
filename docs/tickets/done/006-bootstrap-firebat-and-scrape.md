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

---

## RESOLVED 2026-11-25 — not blocked; firebat was the wrong host

**The blocker was removed by deleting the requirement, not by satisfying it.**

firebat was made the data plane for two reasons, and neither survives scrutiny:

1. *Always-on*, to run a scheduled scraper. But scraping is one-shot by decision
   (no cron), so nothing needs to be always-on. A one-shot pass runs on the Mac.
2. *409 GB disk*. Never measured at the time. Actual size is **~55 KB per Lowyat
   thread**, so 200,000 threads is ~11 GB against the Mac's 58 GB free. The big
   disk was never needed.

And serving needs no host Python either: `llama-server` ships inside the k3s
container image. So firebat's only job is ticket 014, and this ticket's apt
dependency is gone.

**Done:** 398 Lowyat threads scraped locally (~22 MB, 16k+ normalized rows).
`scripts/run_scrapes.sh` runs every enabled source once from the repo root.
`scripts/deploy_firebat.sh` is retained for shipping model artifacts at 014 and
now skips the venv step with a note instead of failing.

### Superseded (kept for the reasoning)

`NEEDS-HUMAN:` two things on firebat need root, and there is no passwordless sudo:

```sh
sudo apt install -y git python3-venv
```

`python3-venv` is the hard blocker — firebat has no `pip`, no `ensurepip`, no `pipx`
and no `uv`, and `/usr/lib/python3.13/EXTERNALLY-MANAGED` is set, so there is no
no-root path to installing dependencies. `git` is optional (`scripts/deploy_firebat.sh`
uses tar-over-ssh instead) but worth having.

Deliberately not worked around: the alternative was downloading and executing a
third-party installer (`get-pip.py` or `uv`) onto the user's homelab server, which
is their decision, not an agent's.

### Already done
- `scripts/deploy_firebat.sh` — tar-over-ssh sync, venv build, verification. Run it
  again after the apt install; it is idempotent and now fails with the exact command
  needed.
- `scripts/run_scrapes.sh` — one-shot runner for all enabled sources, skips Reddit
  cleanly when credentials are absent.
- Code is already synced to `~/lalalm` on firebat; corpus dirs exist at
  `~/lalalm-data`, logs at `~/lalalm-logs`, secrets dir at `~/.config/lalalm`.

### Path change from the original ticket
The ticket specified `/var/lib/lalalm/data` and `/etc/lalalm/env`. Both need root.
Changed to `~/lalalm-data` and `~/.config/lalalm/env`, which preserves the actual
requirement — corpus outside the code checkout, so a stray `git clean` cannot reach
it — without root.
