# lalalm

A Singlish/Manglish corpus, and a Qwen3 LoRA adapter trained on it.

Two deliverables, in order: (1) the **corpus** — the scarce artifact, keeps its value when
the next base model lands; (2) a **fine-tuned adapter** as proof the corpus is useful.

## Start here

1. Read `docs/tickets/README.md`.
2. Take the lowest-numbered ticket in `docs/tickets/todo/` whose `Depends-on` are all in `done/`.
3. Do it. Verify its `Done-when` command exits 0.
4. Commit. Move the file to `done/`.

`git log` is the progress log. A cold session with zero context should cost ~30 seconds to resume.
If a ticket turns out to be blocked, move it to `blocked/` and add a `NEEDS-HUMAN:` line saying
exactly what is required.

## Invariants

Do not violate these without the user changing them here first.

- **Three machines, three jobs.** `firebat` (ssh) scrapes, stores the corpus, and serves the
  model — it has **no usable training GPU** (Intel UHD only), so never try to train there.
  The MacBook Air M1 is dev + small-model MLX training. Modal is for real training runs only.
- **Never commit `data/`.** It is gitignored and stays that way. The full corpus lives on
  firebat (409 GB free); the Mac holds a sampled dev slice capped at ~2 GB.
- **Tag every item with `variety`** (`sg` | `my`) and `register` (`forum` | `spoken` | `social`)
  at scrape time. This is free then and impossible to recover later.
- **Manglish is co-equal, not an afterthought.** The user is Malaysian. `r/malaysia` alone is
  too formal-English; Manglish depth comes from Lowyat and Malaysian YouTube. Track corpus
  saturation **per variety**, because `sg` will saturate long before `my` and a combined number
  would hide exactly that shortfall.
- **Never filter by language ID.** langid/fastText label Singlish as either "English" or
  low-confidence garbage, so a language gate deletes precisely the best text in the corpus.
  Score by **marker density** and use it to rank/weight, never to gate. Keep everything above
  a very low floor.
- **Exact-hash dedup only, never near-dup.** Short `lah`-heavy replies look near-identical to
  MinHash, which will delete the strongest register signal you own.
- **Train from Instruct, never from Base.** The corpus is far too small to rebuild instruction
  following from scratch; starting from Base spends the whole data budget learning to answer
  questions at all. Target Qwen3-4B-Instruct, prove the pipeline on 1.7B first.
- **Scrapers are one-shot and resumable.** No cron, no CronJobs, no timers. Always append-mode
  output plus a `.seen` ID log per source, so an interrupted run is safe to re-run and never
  re-hammers a source from page one.
- **k3s serves the model. That is all it does here.** Scrapers run from a plain venv on firebat.

## Human gates

An agent may prepare these fully, but must stop and hand over:

1. **Reddit API credentials** — only the user can create the app.
2. **Any paid cloud run** (Modal) — money. Write and validate the script, document the exact
   command and expected cost, then stop.
3. **Exposing the inference service beyond Tailscale** — outward-facing.
4. **Deleting or overwriting collected corpus data.**

## Decisions already made (do not re-litigate)

- Reddit comment **tree** is preserved (`parent_id`, `link_id`, `created_utc`). Parent→child
  is a free conversational pair and the score says which replies are good.
- **Two-stage LoRA**: stage 1 register adaptation (r=8, LR ~2e-5, q/k/v/o only, 1 epoch) →
  **merge** → stage 2 behaviour (r=16–32, LR ~1e-4, +MLP, 2–3 epochs). Merging between stages
  lets stage 1 be evaluated on its own.
- **Modal**, not RunPod/Vast: it provisions, runs, and dies, billed per second. A box that
  keeps billing until someone remembers to kill it is the wrong failure mode for unattended runs.
- **Eval**: a hand-written fixed 50-prompt set, marker-frequency compared against held-out human
  corpus (too few markers = undertrained; *more* than humans = overfit into self-parody), plus an
  English instruction-following regression check. The user's private testers are ground truth.
- **Serving**: merge adapter → Q4_K_M GGUF → `llama-server` → k3s Deployment, `memory: 5Gi`
  hard cap (firebat has ~11 GB available and other workloads), hostPath volume for weights,
  Tailscale for access. Keep the 1.7B GGUF as a fallback if 4B feels too slow.
- Access is **private** — a handful of invited testers. Raw scraped text is never redistributed.

## Environment

- `HF_HOME` must be set to an explicit path. The default cache silently keeps both the original
  download and the MLX-converted copy, which is how 58 GB quietly becomes 20 GB.
- Secrets on firebat live in a root-only env file, not a k8s Secret — nothing in the cluster
  needs them.
