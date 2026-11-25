# Tickets

One file per ticket. Status is the directory it lives in: `todo/` → `done/`, or `blocked/` if it
needs something only the user can provide.

**Protocol:** take the lowest-numbered ticket in `todo/` whose `Depends-on` are all in `done/`.
Do it. Verify `Done-when` exits 0. Commit. Move the file. See `CLAUDE.md` for invariants.

No Jira, no GitHub Issues mirror — two trackers means neither is trusted.

## Phases

| | Phase | Tickets |
|---|---|---|
| **P0** | Data plane — scrapers, config, one-shot collection | 001–006 |
| **P1** | Corpus — ingest, clean, score, build training sets | 007–009, 015 |
| **P2** | Smoke train — prove the pipeline free, on the M1 | 010–011 |
| **P3** | Real train — Qwen3-4B on Modal | 012 |
| **P4** | Serve — quantize, deploy to k3s on firebat (container only) | 013–014 |

## Index

| # | Ticket | Depends on | Gate |
|---|---|---|---|
| 001 | Reddit scraper: preserve comment tree, make resumable | — | |
| 002 | `sources.yaml` config with variety + register | — | |
| 003 | Reddit API credentials wizard | — | **human** |
| 004 | YouTube caption scraper: fix ordering + dedup bug | — | |
| 005 | Lowyat.NET forum scraper | 002 | |
| 006 | Run the one-shot scrapes (locally; firebat not needed) | 001–005 | |
| 007 | Ingest + normalize + PII scrub | 006 | |
| 008 | Marker lexicon, density scoring, dedup, saturation report | 007 | |
| 009 | Build stage-1 corpus and stage-2 pair sets | 008 | |
| 010 | Eval harness + hand-written 50-prompt set | — | |
| 011 | MLX two-stage LoRA smoke train on Qwen3-1.7B | 009, 010 | |
| 012 | Modal training script for Qwen3-4B | 011 | **human** |
| 013 | Merge adapter, quantize to Q4_K_M GGUF | 012 | |
| 014 | Serve on k3s via llama-server | 013 | **human** (exposure) |
| 015 | Dialect-dense discovery: target boards, weight by thread | 008 | |

## Dependency shape

```
001 ─┐
002 ─┼─ 005 ─┐
003 ─┤       ├─ 006 ─ 007 ─ 008 ─ 009 ─┐
004 ─┘       │                         ├─ 011 ─ 012* ─ 013 ─ 014*
             └─────────────── 010 ─────┘
```
`*` = human gate. 015 was raised from 008's findings and gates real training quality:
the first 172 threads scored 0.0042 mean marker density with 5% of rows carrying any
marker, so discovery needs fixing before 009's pair set is worth training on.
