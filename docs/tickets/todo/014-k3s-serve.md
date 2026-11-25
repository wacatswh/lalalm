# 014 — Serve on k3s via llama-server

**Phase:** P4 · **Depends-on:** 013 · **Gate:** **HUMAN** (exposure)

`NEEDS-HUMAN:` exposing the service beyond Tailscale is outward-facing and is the user's call.
Deploying it cluster-internal and reachable over Tailscale is in scope for an agent.

## Goal
The model running as a k3s service on firebat, reachable by invited testers over Tailscale.

## Why
k3s earns its keep for exactly this: a long-lived thing that needs a stable endpoint. (It is
deliberately *not* used for the scrapers — those are one-shot and need no rollout strategy.)

The 5 Gi memory cap is not a formality. firebat has ~11 GB available and is already carrying
other workloads; an unbounded inference pod on a bad day takes the cluster down with it.

## Scope
- `deploy/deployment.yaml`: 1 replica, `llama-server`, `memory` request well under a **5 Gi
  limit**, CPU request sized to leave headroom on the 16 threads.
- **hostPath volume** for the GGUF, not baked into the image — swapping model versions must not
  mean an image rebuild.
- `deploy/service.yaml`: ClusterIP. Tailscale for tester access. No Ingress, no public exposure.
- Readiness probe that actually generates a token, not just a TCP check — a loaded-but-wedged
  llama-server passes a port check happily.
- `deploy/README.md`: apply/rollback commands, how to swap the GGUF (including the 1.7B
  fallback), and the measured tokens/sec.

## Done-when
```sh
ssh firebat 'set -e; kubectl get deploy lalalm -o jsonpath="{.status.readyReplicas}" | grep -q 1; \
  kubectl get deploy lalalm -o jsonpath="{.spec.template.spec.containers[0].resources.limits.memory}" \
    | grep -q "5Gi"; echo deployed' && \
ssh firebat 'curl -sf -m 60 http://<svc>/completion -d "{\"prompt\":\"eh bro you makan already?\",\"n_predict\":24}" | head -c 300'
```
The second command must return generated text, and the generation should visibly contain
dialect markers — that is the real end-to-end check.

## Files
`deploy/deployment.yaml`, `deploy/service.yaml`, `deploy/README.md`

## Notes
Measure tokens/sec under a realistic prompt and write it down. Rough expectation on this CPU is
single-digit to low-double-digit tok/s for 4B Q4_K_M. If testers find it too slow, the 1.7B
GGUF from 013 is the lever — not a retrain.
