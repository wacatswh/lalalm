# 007 — Ingest + normalize + PII scrub

**Phase:** P1 · **Depends-on:** 006 · **Gate:** none

## Goal
Fold all three raw sources into one normalized JSONL schema, with PII scrubbed at ingest.

## Why
Three scrapers produce three shapes. Everything downstream — scoring, dedup, pair building,
saturation — should read one schema. Doing the PII scrub here, at the boundary, means no
downstream stage ever sees the raw identifiers.

## Scope
Target schema, one object per line in `data/processed/corpus.jsonl`:
```json
{"uid","source","source_id","parent_uid","thread_uid","text","score","created",
 "variety","register"}
```
- `uid` stable and derived from `source` + `source_id` so re-ingest is idempotent.
- `parent_uid` null for roots. This field is what stage 2's pairs are built from.

PII scrub, regex-based, applied to `text`:
- Usernames/@mentions, `u/name`, `/u/name`
- Emails, URLs (replace with a `<url>` token rather than deleting — URL presence is register signal)
- Phone numbers (MY `01x-xxxxxxx`, SG 8-digit starting 8/9)
- **Malaysian NRIC** (`YYMMDD-PB-####`) and **Singapore NRIC/FIN** (`[STFG]#######[A-Z]`)

## Done-when
```sh
python3 scripts/ingest.py --check && \
python3 -c "import json; \
rows=[json.loads(l) for l in open('data/processed/corpus.jsonl')]; \
import re; \
assert rows, 'empty corpus'; \
need={'uid','source','parent_uid','text','variety','register'}; \
assert all(need <= set(r) for r in rows), 'schema'; \
assert len({r['uid'] for r in rows})==len(rows), 'uid not unique'; \
nric=re.compile(r'\d{6}-\d{2}-\d{4}|[STFG]\d{7}[A-Z]'); \
assert not [r for r in rows if nric.search(r['text'])], 'NRIC leaked'; \
print(len(rows),'rows ok')"
```

## Files
`scripts/ingest.py`

## Notes
This is scrubbing, not an anonymity guarantee. The corpus is still other people's words — which
is why it stays on firebat and is never redistributed (invariant: access is private).
