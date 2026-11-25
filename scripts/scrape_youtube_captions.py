#!/usr/bin/env python3
"""Pull captions/subtitles for YouTube video(s) using yt-dlp.

Usage:
    python3 scrape_youtube_captions.py <youtube_url>
    python3 scrape_youtube_captions.py urls.txt
    (a single video link, or a text file with one URL/ID per line)

Output: data/raw/youtube/<video_id>.txt (plain text, timestamps stripped)
"""
import re
import sys
import subprocess
import tempfile
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "youtube"


def vtt_to_text(vtt_path: Path) -> str:
    lines = vtt_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    seen = set()
    out = []
    for line in lines:
        line = line.strip()
        if not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        if re.match(r"^\d+$", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line and line not in seen:
            seen.add(line)
            out.append(line)
    return "\n".join(out)


def fetch_one(url: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--write-sub",
            "--sub-langs", "en,ms,zh-Hans",
            "--sub-format", "vtt",
            "--sleep-subtitles", "2",
            "--ignore-errors",
            "-o", str(tmp_path / "%(id)s.%(ext)s"),
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        vtt_files = list(tmp_path.glob("*.vtt"))
        if not vtt_files:
            print(f"[no captions] {url}: {result.stderr.strip()[:200]}")
            return

        video_id = vtt_files[0].stem.split(".")[0]
        combined = "\n".join(vtt_to_text(f) for f in vtt_files)
        out_file = OUT_DIR / f"{video_id}.txt"
        out_file.write_text(combined, encoding="utf-8")
        print(f"[ok] {url} -> {out_file.name} ({len(combined)} chars)")


def is_probably_url_or_id(arg: str) -> bool:
    return arg.startswith("http") or (not Path(arg).exists())


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    arg = sys.argv[1]

    if is_probably_url_or_id(arg):
        urls = [arg]
    else:
        urls = [l.strip() for l in Path(arg).read_text().splitlines() if l.strip() and not l.startswith("#")]

    for url in urls:
        fetch_one(url)


if __name__ == "__main__":
    main()
