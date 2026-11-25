# 003 — Reddit API credentials wizard

**Phase:** P0 · **Depends-on:** — · **Gate:** **HUMAN**

`NEEDS-HUMAN:` only the user can create a Reddit app and copy out the client ID and secret.
An agent can write the wizard and verify the credential check, but cannot obtain the values.

## Goal
A script that walks the user through creating a Reddit "script" app in about two minutes and
writes the resulting credentials to a gitignored env file.

## Why
Every Reddit scrape is blocked on these three env vars. Without a guided script this becomes a
recurring "go read the PRAW docs" interruption, and the credentials end up pasted somewhere
they shouldn't be.

## Scope
- `scripts/setup_reddit_creds.sh` — prints the exact URL
  (<https://www.reddit.com/prefs/apps>), states which app type to pick ("script"), what to put
  in the redirect URI field, then prompts for client ID and secret.
- Writes `.env.local` (gitignored) with `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`,
  `REDDIT_USER_AGENT`. Never echo the secret back to the terminal.
- Verifies by making one authenticated read-only call and reporting success or the exact error.
- Add `.env.local` to `.gitignore`.

## Done-when
```sh
grep -q '^\.env\.local$' .gitignore && test -x scripts/setup_reddit_creds.sh && echo ok
```
Plus: the user runs it once and the verification call succeeds.

## Files
`scripts/setup_reddit_creds.sh`, `.gitignore`
