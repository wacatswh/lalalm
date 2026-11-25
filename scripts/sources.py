#!/usr/bin/env python3
"""Loader for sources.yaml. Every scraper reads sources through here."""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / "sources.yaml"

VARIETIES = ("sg", "my")
REGISTERS = ("forum", "spoken", "social")
KINDS = ("reddit", "youtube", "lowyat")


def load(kind: str | None = None, include_unverified: bool = False,
         include_disabled: bool = False) -> list[dict]:
    """Return source entries, validated. Filter by kind if given."""
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    entries = raw.get("sources") or []

    out = []
    for i, e in enumerate(entries):
        where = f"sources.yaml entry {i} ({e.get('name', '?')})"
        for field in ("kind", "name", "variety", "register"):
            if not e.get(field):
                raise ValueError(f"{where}: missing '{field}'")
        if e["kind"] not in KINDS:
            raise ValueError(f"{where}: kind must be one of {KINDS}")
        if e["variety"] not in VARIETIES:
            raise ValueError(f"{where}: variety must be one of {VARIETIES}")
        if e["register"] not in REGISTERS:
            raise ValueError(f"{where}: register must be one of {REGISTERS}")

        e.setdefault("enabled", True)
        e.setdefault("verify", False)

        if not e["enabled"] and not include_disabled:
            continue
        if e["verify"] and not include_unverified:
            continue
        if kind and e["kind"] != kind:
            continue
        out.append(e)
    return out


def balance(entries: list[dict] | None = None) -> dict[str, int]:
    """Source counts per variety. 'Am I collecting enough Manglish?' as a query."""
    entries = load() if entries is None else entries
    return {v: sum(1 for e in entries if e["variety"] == v) for v in VARIETIES}


if __name__ == "__main__":
    all_src = load(include_unverified=True, include_disabled=True)
    print(f"{len(all_src)} sources configured")
    for v, n in balance(all_src).items():
        print(f"  {v}: {n}")
    unver = [e["name"] for e in all_src if e["verify"]]
    if unver:
        print(f"unverified (skipped unless --include-unverified): {', '.join(unver)}")
