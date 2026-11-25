#!/usr/bin/env python3
"""Pull captions for YouTube videos via yt-dlp, preserving utterance order and language.

Two things this deliberately does NOT do, because the previous version did both and
each destroyed the signal we are collecting:

1. It does not dedup repeated lines across a video. Colloquial speech is full of
   repeated short utterances -- "lah", "can can", "aiyo" -- and a seen-set deletes
   precisely the strongest register signal in spoken data. Only *consecutive*
   duplicates are collapsed, because auto-captions genuinely repeat a line across
   overlapping cues.
2. It does not concatenate whole language tracks. Joining an English track to a Malay
   track end-to-end destroys code-switching, which is the most valuable thing in
   Manglish speech. Cues from all tracks are interleaved by timestamp instead.

Usage:
    python3 scrape_youtube_captions.py                  # enabled youtube sources
    python3 scrape_youtube_captions.py <url|id|file>    # ad-hoc video(s)

Output: data/raw/youtube/<source>.jsonl
        {video_id, start, lang, text, variety, register}
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import load

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "youtube"
SUB_LANGS = "en,en-US,en-GB,ms,zh-Hans,zh-Hant,ta"
MAX_VIDEOS_DEFAULT = 50
CUE_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->")
TAG_RE = re.compile(r"<[^>]+>")


def secs(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(path: Path) -> list[tuple[float, str]]:
    """VTT -> [(start_seconds, text)], consecutive duplicates collapsed."""
    cues: list[tuple[float, str]] = []
    start: float | None = None
    buf: list[str] = []

    def flush() -> None:
        if start is None:
            return
        text = " ".join(buf).strip()
        text = TAG_RE.sub("", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text and (not cues or cues[-1][1] != text):
            cues.append((start, text))

    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        m = CUE_RE.search(line)
        if m:
            flush()
            start, buf = secs(*m.groups()), []
            continue
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        buf.append(line)
    flush()
    return cues


def lang_of(vtt: Path) -> str:
    # yt-dlp writes <id>.<lang>.vtt
    parts = vtt.name.split(".")
    return parts[-2] if len(parts) >= 3 else "unknown"


def fetch_video(video: str, tags: dict) -> list[dict]:
    """All caption tracks for one video, interleaved by timestamp."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proc = subprocess.run(
            ["yt-dlp", "--skip-download", "--write-auto-sub", "--write-sub",
             "--sub-langs", SUB_LANGS, "--sub-format", "vtt",
             "--sleep-subtitles", "2", "--ignore-errors",
             "-o", str(tmp_path / "%(id)s.%(ext)s"), video],
            capture_output=True, text=True)

        vtts = sorted(tmp_path.glob("*.vtt"))
        if not vtts:
            print(f"[no captions] {video}: {proc.stderr.strip()[-160:]}")
            return []

        video_id = vtts[0].name.split(".")[0]
        rows: list[dict] = []
        for vtt in vtts:
            lang = lang_of(vtt)
            for start, text in parse_vtt(vtt):
                rows.append({"video_id": video_id, "start": start, "lang": lang,
                             "text": text, **tags})

        # Interleave by time so code-switching between tracks survives.
        rows.sort(key=lambda r: (r["start"], r["lang"]))
        return rows


def list_channel(name: str, limit: int) -> list[str]:
    url = name if name.startswith("http") else f"https://www.youtube.com/{name}/videos"
    proc = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--print", "id",
         "--playlist-end", str(limit), "--ignore-errors", url],
        capture_output=True, text=True)
    ids = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
    if not ids:
        print(f"[warn] {name}: no videos listed. {proc.stderr.strip()[-160:]}")
    return ids


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def scrape(label: str, videos: list[str], tags: dict) -> None:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", label)
    out_file, seen_file = OUT_DIR / f"{safe}.jsonl", OUT_DIR / f"{safe}.seen"
    seen = load_seen(seen_file)
    written = skipped = 0

    with out_file.open("a", encoding="utf-8") as f, seen_file.open("a", encoding="utf-8") as sf:
        for v in videos:
            vid = v.rsplit("/", 1)[-1].split("?")[0] if "/" in v else v
            if vid in seen:
                skipped += 1
                continue
            try:
                rows = fetch_video(v, tags)
            except KeyboardInterrupt:
                print(f"\n[interrupted] {label}: {written} rows written, safe to re-run")
                raise
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            sf.write(vid + "\n")
            sf.flush()
            seen.add(vid)
            written += len(rows)

    print(f"[ok] {label} -> {out_file.name} (+{written} cues, {skipped} videos already done)")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]

    if args:  # ad-hoc: url, id, or a file of them
        videos: list[str] = []
        for a in args:
            p = Path(a)
            if p.is_file():
                videos += [l.strip() for l in p.read_text().splitlines() if l.strip()]
            else:
                videos.append(a)
        scrape("adhoc", videos, {"variety": "sg", "register": "spoken"})
        return

    srcs = load(kind="youtube")
    if not srcs:
        sys.exit("No enabled+verified youtube sources in sources.yaml.\n"
                 "The seeded handles are verify:true until confirmed to resolve; "
                 "see docs/tickets/todo/ for the verification step.")
    for src in srcs:
        tags = {"variety": src["variety"], "register": src["register"]}
        vids = list_channel(src["name"], src.get("max_videos", MAX_VIDEOS_DEFAULT))
        if vids:
            scrape(src["name"], vids, tags)


if __name__ == "__main__":
    main()
