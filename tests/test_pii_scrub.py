"""Prove 007: PII patterns are scrubbed, and register-bearing text is not mangled.

Every identifier below is deliberately INVALID-but-well-formed (all-zero NRIC and
phone, .invalid TLD) rather than merely fabricated. This file is public, and a
realistic-looking NRIC could coincidentally belong to a real person.
"""
import sys
sys.path.insert(0, "scripts")
from ingest import scrub

cases = [
    ("my ic is 000000-00-0000 ok", "<nric>"),
    ("nric S0000000A lah", "<nric>"),
    ("email me at nobody+test@example.invalid", "<email>"),
    ("see https://example.com/thing for more", "<url>"),
    ("call 010-000 0000 can", "<phone>"),
    ("my hp 80000000 ah", "<phone>"),
    ("thanks u/exampleuser for the tip", "<user>"),
    ("cc @someone.else here", "<user>"),
]
for text, token in cases:
    got = scrub(text)
    assert token in got, f"{text!r} -> {got!r} (expected {token})"
    assert not any(c.isdigit() for c in got.replace(token, "")) or token in ("<url>", "<user>"), \
        f"digits survived: {got!r}"

# Must NOT mangle dialect text, including numbers that are not identifiers.
keep = [
    "wah the nasi lemak only 5 ringgit sia",
    "aiyo 2026 already still like that meh",
    "boleh tahan lah, RM 1200 per month",
]
for text in keep:
    got = scrub(text)
    assert "<" not in got, f"over-scrubbed: {text!r} -> {got!r}"

print("PASS: all PII patterns scrubbed, dialect text intact")
for text, _ in cases[:4]:
    print(f"   {text!r}\n-> {scrub(text)!r}")
