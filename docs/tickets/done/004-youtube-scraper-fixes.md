# 004 — YouTube caption scraper: fix ordering + dedup bug

**Phase:** P0 · **Depends-on:** — · **Gate:** none

## Goal
Make `scripts/scrape_youtube_captions.py` preserve utterance order and stop deleting repeated
lines, and make it resumable.

## Why
Two real bugs, both of which damage exactly the data we want:

1. The `seen` set drops any caption line that has appeared before in the video. Colloquial
   speech is *full* of repeated short utterances — "lah", "can can", "aiyo" — so this silently
   deletes the strongest register signal in spoken data.
2. Captions from multiple languages are joined with `"\n".join(...)` across whole files, so an
   English track and a Malay track end up concatenated rather than interleaved by time. Any
   code-switching, which is the most valuable thing in Manglish speech, is destroyed.

## Scope
- Remove the `seen` dedup entirely. Keep consecutive-duplicate collapsing only (auto-captions
  genuinely repeat the same line across overlapping cues).
- Parse cue start times; emit records ordered by timestamp with the source language tagged, so
  code-switching survives. Output JSONL, not flat text, to match the other scrapers:
  `{video_id, start, lang, text, variety, register}`.
- `.seen` log of completed video IDs; skip on restart; append-mode output.
- Read the channel/video list from `sources.yaml` (002) when available; keep the file/URL
  argument form working.

## Done-when
```sh
python3 -c "import ast; src=open('scripts/scrape_youtube_captions.py').read(); \
assert 'seen' not in src or 'consecutive' in src.lower(); \
assert '.seen' in src and 'start' in src; ast.parse(src); print('ok')"
```
Plus: scrape one known code-switching video and confirm by eye that English and Malay lines
interleave in timestamp order.

## Files
`scripts/scrape_youtube_captions.py`

## Notes
The existing `data/raw/youtube/dQw4w9WgXcQ.txt` is a Rickroll smoke test. Delete it — it is not
corpus. (Covered by invariant 4: this is test output, not collected data.)
