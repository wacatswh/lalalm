#!/usr/bin/env bash
# Run every enabled source once. Safe to re-run: each scraper is append-only with
# a .seen log, so this resumes rather than restarting.
#
# ONE-SHOT BY DESIGN. Do not wrap this in cron, a systemd timer, or a k3s CronJob
# (project invariant) -- it is triggered deliberately when a source is added.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
PY="$REPO_ROOT/.venv/bin/python"
LOGDIR="${LALALM_LOGS:-$HOME/lalalm-logs}"
mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%dT%H%M%S)"

# Secrets, if present. Reddit is skipped without them rather than failing the run.
for f in "$HOME/.config/lalalm/env" "$REPO_ROOT/.env.local"; do
  [ -r "$f" ] && { set -a; . "$f"; set +a; }
done

MAX_THREADS="${LOWYAT_MAX:-500}"
rc=0

run() {
  local name="$1"; shift
  local log="$LOGDIR/${STAMP}-${name}.log"
  echo "==> $name (log: $log)"
  if "$@" >>"$log" 2>&1; then
    tail -2 "$log" | sed 's/^/    /'
  else
    echo "    FAILED (see $log)"; tail -5 "$log" | sed 's/^/    /'; rc=1
  fi
}

if [ -n "${REDDIT_CLIENT_ID:-}" ]; then
  run reddit "$PY" scripts/scrape_reddit.py
else
  echo "==> reddit SKIPPED: no credentials. Run scripts/setup_reddit_creds.sh"
  echo "    (this is the project's documented human gate, not a failure)"
fi

run lowyat "$PY" scripts/scrape_lowyat.py --max "$MAX_THREADS"

if "$PY" -c "import sys;sys.path.insert(0,'scripts');from sources import load;sys.exit(0 if load(kind='youtube') else 1)" 2>/dev/null; then
  run youtube "$PY" scripts/scrape_youtube_captions.py
else
  echo "==> youtube SKIPPED: all channels still verify:true in sources.yaml"
fi

echo
echo "==> corpus state"
find "$REPO_ROOT/data/raw" -name '*.jsonl' -exec sh -c 'printf "    %-44s %s lines\n" "$1" "$(wc -l < "$1")"' _ {} \;
exit $rc
