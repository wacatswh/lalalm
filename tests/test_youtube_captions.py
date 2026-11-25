"""Prove 004: repeated utterances survive, and language tracks interleave by time."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, "scripts")
import scrape_youtube_captions as yt

EN = """WEBVTT

1
00:00:01.000 --> 00:00:02.000
can lah

2
00:00:02.000 --> 00:00:03.000
can lah

3
00:00:05.000 --> 00:00:06.000
<c>wah</c> so expensive

4
00:00:07.000 --> 00:00:08.000
can lah
"""

MS = """WEBVTT

1
00:00:03.500 --> 00:00:04.500
tapi mahal sikit

2
00:00:06.500 --> 00:00:07.000
betul tu
"""

with tempfile.TemporaryDirectory() as t:
    d = Path(t)
    (d / "vid1.en.vtt").write_text(EN)
    (d / "vid1.ms.vtt").write_text(MS)

    en = yt.parse_vtt(d / "vid1.en.vtt")
    texts = [x[1] for x in en]

    # Bug 1: a seen-set would have deleted the 3rd "can lah" entirely.
    assert texts.count("can lah") == 2, f"expected 2 (consecutive pair collapsed to 1, plus the later one), got {texts}"
    assert "wah so expensive" in texts, "inline <c> tags not stripped"
    assert yt.lang_of(d / "vid1.ms.vtt") == "ms"

    # Bug 2: tracks must interleave by timestamp, not concatenate.
    rows = []
    for f in sorted(d.glob("*.vtt")):
        rows += [{"start": s, "lang": yt.lang_of(f), "text": x} for s, x in yt.parse_vtt(f)]
    rows.sort(key=lambda r: (r["start"], r["lang"]))
    langs = [r["lang"] for r in rows]

    assert langs != sorted(langs, key=lambda l: l != "en"), "tracks are concatenated, not interleaved"
    assert "ms" in langs[:len(langs) - 1] and langs.index("ms") < langs.index("en", langs.index("ms")), \
        f"no code-switch alternation detected: {langs}"
    print("PASS: repeats kept ->", texts)
    print("PASS: interleaved   ->", [(r["start"], r["lang"]) for r in rows])
