#!/usr/bin/env python3
"""Marker density. Shared by eval (010) and corpus scoring (008)."""
import re
from functools import lru_cache
from pathlib import Path

import yaml

LEXICON = Path(__file__).resolve().parent.parent / "lexicon" / "markers.yaml"


@lru_cache(maxsize=1)
def lexicon() -> dict[str, list[str]]:
    return yaml.safe_load(LEXICON.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def pattern(variety: str | None = None) -> re.Pattern:
    lex = lexicon()
    terms = list(lex.get("both", []))
    if variety in ("sg", "my"):
        terms += lex.get(variety, [])
    else:
        terms += lex.get("sg", []) + lex.get("my", [])
    # Longest first so "macam mana" wins over "macam"; \b both ends avoids
    # matching "lah" inside "blah" or "mah" inside "mahal".
    terms.sort(key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b", re.I)


def tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z']+", text)


def hits(text: str, variety: str | None = None) -> list[str]:
    return [m.group(0).lower() for m in pattern(variety).finditer(text)]


def density(text: str, variety: str | None = None) -> float:
    n = len(tokens(text))
    return len(hits(text, variety)) / n if n else 0.0
