#!/usr/bin/env bash
# Sync this repo to firebat and (re)build its venv.
#
# Uses tar-over-ssh rather than git, because firebat has no git installed and no
# passwordless sudo to install it. Nothing here needs root.
#
# Layout on firebat (deliberately NOT the /var/lib path first sketched in ticket
# 006 -- that needed root. The requirement was that the corpus live outside the
# code checkout so a stray `git clean` cannot reach it; a sibling dir does that):
#   ~/lalalm         code
#   ~/lalalm-data    corpus          <- data/ in the checkout symlinks here
#   ~/lalalm-logs    scrape logs
#   ~/.config/lalalm/env   secrets, mode 600
set -euo pipefail

HOST="${1:-firebat}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> preparing $HOST"
ssh "$HOST" 'mkdir -p ~/lalalm ~/lalalm-data/raw/{reddit,youtube,forums} ~/lalalm-data/processed ~/lalalm-logs ~/.config/lalalm && chmod 700 ~/.config/lalalm'

echo "==> syncing code (excluding data, venv, git)"
tar -C "$REPO_ROOT" -czf - \
    --exclude='.git' --exclude='.venv' --exclude='data' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='.env.local' . \
  | ssh "$HOST" 'tar -C ~/lalalm -xzf -'

echo "==> linking corpus dir"
ssh "$HOST" 'rm -rf ~/lalalm/data && ln -sfn ~/lalalm-data ~/lalalm/data'

# Host Python is OPTIONAL. firebat only serves the model, as a k3s container that
# carries its own runtime -- see ticket 014. The venv below matters only if you
# ever want to run a scraper ON firebat, which the one-shot strategy does not need.
if ! ssh "$HOST" 'python3 -c "import ensurepip"' >/dev/null 2>&1; then
  echo "==> skipping venv: python3-venv absent on $HOST"
  echo "    Not a problem -- firebat serves a container and needs no host Python."
  echo "    Only if you want to scrape FROM firebat: sudo apt install -y python3-venv"
  echo "==> code synced; done"
  exit 0
fi

echo "==> building venv (optional)"
ssh "$HOST" 'cd ~/lalalm && { [ -d .venv ] || python3 -m venv .venv; } && \
  ./.venv/bin/pip install -q --upgrade pip && \
  ./.venv/bin/pip install -q -r requirements.txt && \
  ./.venv/bin/python -c "import yaml,praw,bs4,requests,lxml; print(\"deps ok\")"'

echo "==> verifying"
ssh "$HOST" 'cd ~/lalalm && ./.venv/bin/python scripts/sources.py && df -h ~/lalalm-data | tail -1'
echo "==> done"
