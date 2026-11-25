# 012 — Modal training script for Qwen3-4B

**Phase:** P3 · **Depends-on:** 011 · **Gate:** **HUMAN**

`NEEDS-HUMAN:` launching this costs money. An agent writes the script, validates it, documents
the exact command and the expected cost — **and stops there.** Do not launch a paid run.

## Goal
A committed, reviewed Modal script that runs the same two-stage LoRA on Qwen3-4B-Instruct,
ready for the user to launch.

## Why
Modal over RunPod/Vast is a deliberate choice and it is about failure modes, not price. Modal
provisions, runs the function, and dies, billed per second. A rented box keeps billing until
someone remembers to kill it — exactly wrong when a session can be cut off mid-run by a usage
limit. The per-GPU-hour saving elsewhere is a few dollars; a forgotten pod is not.

## Scope
- `modal/train.py` — container image, dependencies pinned, GPU class, both stages as separate
  entrypoints so stage 2 can be re-run without redoing stage 1.
- Corpus in: upload the training sets as a Modal Volume. Adapters out: download to the repo,
  gitignored.
- **Checkpoint to the Volume every N steps**, and support `--resume`. A run that dies at hour
  three must not restart from zero — the same reasoning as the scrapers' `.seen` logs.
- Run 010's eval as the final step of the job, so results land even if nobody is watching.
- `modal/README.md`: exact launch command, expected wall-clock, **expected cost with the
  arithmetic shown**, and how to confirm the job actually exited.
- Validate without spending: `modal run --detach` dry path, or the smallest possible
  configuration on the smallest data slice, and say plainly in the ticket log which was used.

## Done-when
```sh
python3 -c "import ast; ast.parse(open('modal/train.py').read()); print('parses')" && \
grep -q 'resume' modal/train.py && \
grep -Eqi 'cost|\$' modal/README.md && \
echo "ok — now STOP. Launching is the user's call."
```

## Files
`modal/train.py`, `modal/README.md`

## Notes
Expect single-digit GPU-hours on one A100-class card for the token budget in 009. State the
number in `modal/README.md` rather than leaving the user to infer it.
