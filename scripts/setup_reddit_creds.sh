#!/usr/bin/env bash
# Guided setup for Reddit API credentials. Takes about two minutes.
# Writes .env.local (gitignored). Never echoes the secret back to the terminal.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env.local"
PY="$REPO_ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
dim()  { printf '\033[2m%s\033[0m\n' "$1"; }

bold "Reddit API credentials for lalalm"
echo
echo "Reddit's API is free, but it needs an app registered to your account."
echo "Only you can do this part -- the credentials are yours, not the project's."
echo
bold "Step 1 of 3 -- create the app"
echo "  1. Open:  https://www.reddit.com/prefs/apps"
echo "  2. Scroll to the bottom, click 'create another app...'"
echo "  3. Fill it in:"
echo "       name          lalalm-scraper   (anything)"
dim  "       type          >>> script <<<   (IMPORTANT: not 'web app', not 'installed app')"
echo "       description   leave blank"
echo "       about url     leave blank"
echo "       redirect uri  http://localhost:8080"
dim  "                     (unused for script apps, but the form requires a value)"
echo "  4. Click 'create app'."
echo
echo "You'll then see the app box. The client ID is the short string directly"
echo "under the app name -- NOT labelled, easy to miss. The secret is next to"
echo "the word 'secret'."
echo
read -r -p "Press Enter once the app exists... " _
echo

bold "Step 2 of 3 -- paste the credentials"
read -r -p "  client ID: " CLIENT_ID
read -r -s -p "  client secret (hidden): " CLIENT_SECRET; echo
read -r -p "  your Reddit username (for the user-agent string): " RUSER

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ] || [ -z "$RUSER" ]; then
  echo "All three values are required. Nothing written." >&2
  exit 1
fi
USER_AGENT="lalalm-scraper/0.1 by u/${RUSER}"
echo

bold "Step 3 of 3 -- verify"
if ! REDDIT_CLIENT_ID="$CLIENT_ID" REDDIT_CLIENT_SECRET="$CLIENT_SECRET" \
     REDDIT_USER_AGENT="$USER_AGENT" "$PY" - <<'PYEOF'
import os, sys
try:
    import praw
except ImportError:
    sys.exit("praw not installed. Run: .venv/bin/pip install -r requirements.txt")
try:
    r = praw.Reddit(client_id=os.environ["REDDIT_CLIENT_ID"],
                    client_secret=os.environ["REDDIT_CLIENT_SECRET"],
                    user_agent=os.environ["REDDIT_USER_AGENT"],
                    check_for_async=False)
    post = next(r.subreddit("singapore").hot(limit=1))
    print(f"  authenticated OK -- read r/singapore, got post {post.id}")
except Exception as e:
    sys.exit(f"  FAILED: {type(e).__name__}: {e}\n"
             "  Most common cause: app type is not 'script', or the client ID was\n"
             "  copied from the wrong line (it sits unlabelled under the app name).")
PYEOF
then
  echo
  echo "Credentials NOT saved. Fix the above and re-run." >&2
  exit 1
fi

umask 077
cat > "$ENV_FILE" <<EOF
# Reddit API credentials. Gitignored. Created by scripts/setup_reddit_creds.sh
REDDIT_CLIENT_ID=$CLIENT_ID
REDDIT_CLIENT_SECRET=$CLIENT_SECRET
REDDIT_USER_AGENT=$USER_AGENT
EOF
chmod 600 "$ENV_FILE"

echo
bold "Done."
echo "  Wrote $ENV_FILE (mode 600, gitignored)"
echo "  Use it:  set -a; source .env.local; set +a"
echo "  Then:    .venv/bin/python scripts/scrape_reddit.py"
