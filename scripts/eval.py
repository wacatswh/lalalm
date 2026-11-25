#!/usr/bin/env python3
"""Fixed-set eval: marker frequency, regression pass rate, comparable across runs.

Three layers, because "does it sound Singlish?" judged by reading a few outputs
will mislead by run three:

  1. marker frequency vs a held-out human baseline. Too few markers means
     undertrained. Suspiciously MORE than humans use means overfit into
     self-parody, which a human skim does not catch.
  2. an English instruction-following regression check, for catastrophic
     forgetting from stage 1.
  3. generation samples, because the user's testers are the real ground truth.

Usage:
    python3 eval.py --backend stub --run-id smoke-stage1
    python3 eval.py --backend mlx  --model <path> --adapter <path> --run-id s2
    python3 eval.py --backend http --endpoint http://host:8080 --run-id served
    python3 eval.py --compare smoke-stage1 smoke-stage2
"""
import argparse
import json
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import markers

ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = ROOT / "eval"
RESULTS = EVAL_DIR / "results"


# ---------------------------------------------------------------- backends
def gen_stub(prompt: str, **_) -> str:
    """Deterministic fake generation. Exists so the harness is verifiable before
    any model is trained -- not a model, and never reported as one."""
    rnd = random.Random(prompt)
    tail = rnd.choice(["lah", "lor", "one", "sia", "boleh", "mah"])
    return f"wah ok {prompt.split()[0] if prompt.split() else 'eh'} can {tail}, no problem {tail}"


def gen_mlx(prompt: str, model: str, adapter: str | None = None, **_) -> str:
    from mlx_lm import generate, load
    m, tok = load(model, adapter_path=adapter)
    msgs = [{"role": "user", "content": prompt}]
    text = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    return generate(m, tok, prompt=text, max_tokens=128, verbose=False)


def gen_http(prompt: str, endpoint: str, **_) -> str:
    import requests
    r = requests.post(f"{endpoint.rstrip('/')}/completion",
                      json={"prompt": prompt, "n_predict": 128}, timeout=120)
    r.raise_for_status()
    return r.json().get("content", "")


BACKENDS = {"stub": gen_stub, "mlx": gen_mlx, "http": gen_http}


# ---------------------------------------------------------------- baseline
def human_baseline(path: Path | None) -> dict[str, float | None]:
    """Marker density of real human text, per variety. The number the model is
    measured against -- without it, 'enough markers' has no reference point."""
    out: dict[str, list[float]] = {"sg": [], "my": []}
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            v, t = row.get("variety"), row.get("text", "")
            if v in out and t:
                out[v].append(markers.density(t, v))
    return {v: (statistics.mean(d) if d else None) for v, d in out.items()}


# ---------------------------------------------------------------- run
def run_eval(backend: str, run_id: str, baseline: Path | None, **kw) -> dict:
    gen = BACKENDS[backend]
    prompts = yaml.safe_load((EVAL_DIR / "prompts.yaml").read_text())["prompts"]
    regress = yaml.safe_load((EVAL_DIR / "regression.yaml").read_text())["prompts"]

    gens, dens = [], {"sg": [], "my": []}
    for p in prompts:
        out = gen(p["text"], **kw)
        d = markers.density(out, p["variety"])
        dens[p["variety"]].append(d)
        gens.append({"id": p["id"], "variety": p["variety"], "scenario": p["scenario"],
                     "prompt": p["text"], "output": out, "density": round(d, 4),
                     "markers": markers.hits(out, p["variety"])})

    rg, passed = [], 0
    for r in regress:
        out = gen(r["text"], **kw)
        low = out.lower()
        reasons = []
        inc = r.get("must_include")
        if inc and not any(s.lower() in low for s in inc):
            reasons.append(f"missing any of {inc}")
        d = markers.density(out)
        if "max_marker_density" in r and d > r["max_marker_density"]:
            reasons.append(f"marker density {d:.3f} > {r['max_marker_density']}")
        w = len(out.split())
        if "min_words" in r and w < r["min_words"]:
            reasons.append(f"{w} words < {r['min_words']}")
        if "max_words" in r and w > r["max_words"]:
            reasons.append(f"{w} words > {r['max_words']}")
        ok = not reasons
        passed += ok
        rg.append({"id": r["id"], "pass": ok, "reasons": reasons, "output": out})

    base = human_baseline(baseline)
    result = {
        "run_id": run_id, "backend": backend,
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": {k: str(v) for k, v in kw.items()},
        "marker_freq": {v: round(statistics.mean(d), 4) for v, d in dens.items() if d},
        "human_baseline": {k: (round(v, 4) if v is not None else None) for k, v in base.items()},
        "regression_pass_rate": round(passed / len(regress), 3),
        "regression": rg, "generations": gens,
    }
    if backend == "stub":
        result["WARNING"] = "stub backend: harness self-test only, not model output"

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{run_id}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    (RESULTS / f"{run_id}.md").write_text(summarise(result))
    return result


def verdict(got: float, base: float | None) -> str:
    if base is None:
        return "no baseline"
    ratio = got / base if base else 0
    if ratio < 0.5:
        return f"UNDERTRAINED ({ratio:.2f}x human)"
    if ratio > 1.6:
        return f"SELF-PARODY ({ratio:.2f}x human)"
    return f"ok ({ratio:.2f}x human)"


def summarise(r: dict) -> str:
    L = [f"# eval `{r['run_id']}`", "",
         f"backend `{r['backend']}` · {r['when']}", ""]
    if "WARNING" in r:
        L += [f"> **{r['WARNING']}**", ""]
    L += ["## Marker frequency", "",
          "| variety | model | human | verdict |", "|---|---|---|---|"]
    for v in ("sg", "my"):
        if v in r["marker_freq"]:
            b = r["human_baseline"].get(v)
            L.append(f"| {v} | {r['marker_freq'][v]:.4f} | "
                     f"{b if b is not None else '—'} | {verdict(r['marker_freq'][v], b)} |")
    L += ["", f"## Regression: {r['regression_pass_rate']:.0%} pass", ""]
    for x in r["regression"]:
        if not x["pass"]:
            L.append(f"- `{x['id']}` FAIL — {'; '.join(x['reasons'])}")
    L += ["", "## Samples", ""]
    for g in r["generations"][:8]:
        L += [f"**{g['id']}** ({g['variety']}/{g['scenario']}) `{g['prompt']}`",
              f"> {g['output']}", ""]
    return "\n".join(L)


def compare(a: str, b: str) -> None:
    ra = json.loads((RESULTS / f"{a}.json").read_text())
    rb = json.loads((RESULTS / f"{b}.json").read_text())
    print(f"{'metric':<28}{a:>16}{b:>16}{'delta':>12}")
    print("-" * 72)
    for v in ("sg", "my"):
        x, y = ra["marker_freq"].get(v), rb["marker_freq"].get(v)
        if x is not None and y is not None:
            print(f"{'marker_freq ' + v:<28}{x:>16.4f}{y:>16.4f}{y - x:>+12.4f}")
    x, y = ra["regression_pass_rate"], rb["regression_pass_rate"]
    print(f"{'regression_pass_rate':<28}{x:>16.3f}{y:>16.3f}{y - x:>+12.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=list(BACKENDS), default="stub")
    ap.add_argument("--run-id")
    ap.add_argument("--model"); ap.add_argument("--adapter"); ap.add_argument("--endpoint")
    ap.add_argument("--baseline", type=Path,
                    default=ROOT / "data" / "processed" / "holdout.jsonl")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
    a = ap.parse_args()

    if a.compare:
        compare(*a.compare)
        return
    if not a.run_id:
        ap.error("--run-id required")

    kw = {k: v for k, v in (("model", a.model), ("adapter", a.adapter),
                            ("endpoint", a.endpoint)) if v}
    r = run_eval(a.backend, a.run_id, a.baseline, **kw)
    print(summarise(r))


if __name__ == "__main__":
    main()
