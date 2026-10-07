"""
Elon's source list and transcript reader (used by rebuild_elon.py).

sources(): one entry per source with its title, date and link, written to
data/elon_sources.json. Interview dates and titles come from the videos'
YouTube pages (fetched once; refresh with `python rebuild_elon.py --refresh-sources`).
97% of non-tweet memories used to be dated "unknown", so time travel to
2021-2023 returned only tweets.

read_transcript(): the raw transcripts as timed sentences, with the
speaker when the transcript names one. The old pipeline used hand-cleaned
copies that had lost every timestamp and link, every "like" (including
real ones: "I'd to just give a heartfelt thanks"), and were cut into
80-word windows, so 44% of interview chunks ended mid-sentence.
"""

from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_INTERVIEWS = ROOT / "01-Raw-Data" / "Interviews"
SOURCES_PATH = ROOT / "data" / "elon_sources.json"

# Not on YouTube with a link in the transcript: from the show's own release
MANUAL = {
    "Don Lemon.txt": {"title": "The Don Lemon Show: Elon Musk", "date": "2024-03-18", "url": None,
                      "note": "Aired on YouTube and podcast platforms on 18 March 2024; the transcript has no video link."},
}
BOOKS = {
    "Elon Musk (Walter Isaacson).pdf": {"title": "Elon Musk, by Walter Isaacson", "date": "2023-09-12", "kind": "book"},
    "Isaacson-Quotes-cleaned.md": {"title": "Quotes from Elon Musk, by Walter Isaacson", "date": "2023-09-12", "kind": "book"},
    "Vance-Quotes-cleaned.md": {"title": "Quotes from Elon Musk: Tesla, SpaceX, and the Quest for a Fantastic Future, "
                                         "by Ashlee Vance", "date": "2015-05-19", "kind": "book"},
}
# Speaker labels in the two transcripts that have them
_LABEL_TED = re.compile(r"\b(Chris Anderson|CA|Elon Musk|EM):\s")
_LABEL_REV = re.compile(r"^([A-Z][A-Za-z .'-]{1,40}) \((\d{1,2}:\d{2}(?::\d{2})?)\):\s*$")
_TACTIQ_LINE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.\d+\s+(.*)$")
_YOUTUBE_ID = re.compile(r"youtube\.com/watch[/?](?:v=)?([\w-]{11})")
_CAPTION_TAGS = re.compile(r"\[(?:Music|Applause|Laughter|Cheering|__\s*|\s*_+\s*)\]", re.IGNORECASE)
# Unpunctuated captions: a piece ends at a pause (seconds between caption lines)
# once it has CAPTION_WORDS words, and always by CAPTION_MAX_WORDS
CAPTION_WORDS, CAPTION_PAUSE, CAPTION_MAX_WORDS = 35, 3, 70


def _seconds(stamp: str) -> int:
    parts = [int(p) for p in stamp.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _youtube_page(video_id: str) -> dict:
    import requests

    page = requests.get(f"https://www.youtube.com/watch?v={video_id}", timeout=30,
                        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"}).text
    date = re.search(r'"uploadDate":"(\d{4}-\d{2}-\d{2})', page) or re.search(r'"publishDate":"(\d{4}-\d{2}-\d{2})', page)
    title = re.search(r'<meta name="title" content="([^"]+)"', page)
    return {"date": date.group(1) if date else None, "title": html.unescape(title.group(1)) if title else None}


def sources(refresh: bool = False) -> dict:
    """{file name: {title, date, url, kind, video_id?}}, cached in data/elon_sources.json."""
    if SOURCES_PATH.exists() and not refresh:
        return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    found = {}
    for path in sorted(RAW_INTERVIEWS.glob("*.txt")):
        if path.name in MANUAL:
            found[path.name] = {"kind": "interview", **MANUAL[path.name]}
            continue
        head = path.read_text(encoding="utf-8", errors="ignore").split("\n", 4)[:3]
        video = _YOUTUBE_ID.search(" ".join(head))
        if not video:
            continue
        info = _youtube_page(video.group(1))
        time.sleep(1)
        header_title = head[1].lstrip("# ").strip() if len(head) > 1 else ""
        found[path.name] = {"kind": "interview", "video_id": video.group(1),
                            "url": f"https://www.youtube.com/watch?v={video.group(1)}",
                            "title": info["title"] or (header_title if header_title != "No title found" else path.stem),
                            "date": info["date"]}
    found.update(BOOKS)
    SOURCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOURCES_PATH.write_text(json.dumps(found, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return found


def _lines(path: Path) -> list[tuple[int, str | None, str]]:
    """(seconds, speaker or None, text) for each line of a raw transcript."""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    out: list[tuple[int, str | None, str]] = []
    if _LABEL_REV.search(raw.split("\n", 1)[0]):  # Rev format: "Elon Musk (01:12):" then the text
        speaker, at = None, 0
        for line in raw.splitlines():
            label = _LABEL_REV.match(line.strip())
            if label:
                speaker, at = label.group(1), _seconds(label.group(2))
            elif re.fullmatch(r"\((\d{1,2}:\d{2}(?::\d{2})?)\)", line.strip()):
                at = _seconds(line.strip()[1:-1])
            elif line.strip():
                out.append((at, speaker, line.strip()))
        return out
    speaker = None
    for line in raw.splitlines():
        m = _TACTIQ_LINE.match(line.strip())
        if not m:
            continue
        at, text = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)), m.group(4)
        # TED's transcript names who speaks ("CA: ...", "Elon Musk: ...")
        parts = _LABEL_TED.split(text)
        if len(parts) > 1:
            if parts[0].strip():
                out.append((at, speaker, parts[0].strip()))
            for name, piece in zip(parts[1::2], parts[2::2]):
                speaker = "Elon Musk" if name in ("Elon Musk", "EM") else "Chris Anderson"
                if piece.strip():
                    out.append((at, speaker, piece.strip()))
        else:
            out.append((at, speaker, text))
    return out


def is_punctuated(lines: list[tuple[int, str | None, str]]) -> bool:
    """False for raw auto-captions, which have (almost) no sentence ends."""
    words = sum(len(text.split()) for _, _, text in lines)
    ends = sum(len(re.findall(r"[.!?](?:\s|$)", text)) for _, _, text in lines)
    return ends * 100 >= words  # at least one sentence end per 100 words


def read_transcript(path: Path) -> tuple[list[dict], bool]:
    """(sentences, has_speaker_labels): each sentence {"text", "start", "speaker", "punctuated"}.

    Only caption tags ("[Music]", a bleeped "[ __ ]") are removed; every
    spoken word stays. Filler and stutter cleanup happens when a quote is
    shown (services/mix_method.py clean_for_display), never in the data.

    Raw auto-captions have no punctuation, so they would be one "sentence"
    of 10,000+ words (four interviews were a single memory whose search
    vector saw only its first ~200 words). Those are cut between caption
    lines instead: at a pause once a piece has CAPTION_WORDS words, and
    always by CAPTION_MAX_WORDS.
    """
    lines = _lines(path)
    labelled = any(speaker for _, speaker, _ in lines)
    punctuated = is_punctuated(lines)
    sentences: list[dict] = []
    buffer, start, speaker, last_at = "", 0, None, 0
    for at, who, text in lines:
        text = re.sub(r"\s+", " ", _CAPTION_TAGS.sub(" ", text)).strip()
        if not text:
            continue
        words = len(buffer.split())
        cut = not punctuated and buffer and (
            (words >= CAPTION_WORDS and at - last_at >= CAPTION_PAUSE) or words >= CAPTION_MAX_WORDS)
        last_at = at
        if (who != speaker or cut) and buffer:  # a new speaker always starts a new sentence
            sentences.append({"text": buffer.strip(), "start": start, "speaker": speaker})
            buffer = ""
        if not buffer:
            start, speaker = at, who
        buffer += " " + text
        # Emit every complete sentence; keep the unfinished end for the next line
        pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“‘(])", buffer.strip())
        for piece in pieces[:-1]:
            sentences.append({"text": piece.strip(), "start": start, "speaker": speaker})
            start = at
        buffer = pieces[-1]
    if buffer.strip():
        sentences.append({"text": buffer.strip(), "start": start, "speaker": speaker})
    for sentence in sentences:
        sentence["punctuated"] = punctuated
    return sentences, labelled


def watch_link(url: str | None, seconds: int) -> str | None:
    return f"{url}&t={seconds}s" if url else None


def clock(seconds: int) -> str:
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
