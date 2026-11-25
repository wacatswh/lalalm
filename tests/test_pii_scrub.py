"""Prove 007: PII patterns are scrubbed, and register-bearing text is not mangled."""
import sys
sys.path.insert(0, "scripts")
from ingest import scrub

cases = [
    ("my ic is 880101-14-5523 ok", "<nric>"),
    ("nric S1234567D lah", "<nric>"),
    ("email me at foo.bar+x@example.com", "<email>"),
    ("see https://example.com/thing for more", "<url>"),
    ("call 012-345 6789 can", "<phone>"),
    ("my hp 91234567 ah", "<phone>"),
    ("thanks u/someuser for the tip", "<user>"),
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
