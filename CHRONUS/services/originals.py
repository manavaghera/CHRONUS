"""
Show the original: what a custom model's memory came from, not only its text.

* Voice notes: each memory keeps where it starts and ends in the recording
  (audio_start, audio_end), so its source can play exactly that moment.
  Transcribed on this computer (faster-whisper, services/stt.py).
* Photos and scanned letters (.jpg .png .webp, and PDFs with no text layer)
  are read with text recognition that runs on this computer: Tesseract when
  it is installed (it also reads Hindi and Gujarati), else RapidOCR
  (pip install rapidocr-onnxruntime; English). The image stays viewable.

    GET /personas/{id}/uploads/{filename}/original   the uploaded file itself (custom models)
"""

from __future__ import annotations

import io
import shutil
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam
from fastapi.responses import FileResponse

from services import personas as ps

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_MAGIC = {".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG",), ".webp": (b"RIFF",)}
_MEDIA = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".webm": "audio/webm",
          ".flac": "audio/flac", ".aac": "audio/aac", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
          ".webp": "image/webp", ".pdf": "application/pdf"}
PARAGRAPH_CHARS = 400  # one memory per ~70 words of speech, so its time span is exact
# Tesseract's languages (eng, hin, guj .traineddata from github.com/tesseract-ocr/tessdata),
# here because its own folder under Program Files needs admin rights to add to (git-ignored)
TESSDATA_DIR = Path(__file__).resolve().parent.parent / "models" / ".tessdata"
_WINDOWS_TESSERACT = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")  # the installer doesn't add it to PATH


def transcribe(data: bytes) -> list[dict]:
    """A voice note as records of spoken text, each with its time in the recording."""
    from services import stt

    if not stt.available():
        raise ValueError("Audio uploads need local speech recognition: pip install faster-whisper")
    # word times: plain segment ends often run on to where the next one starts, across pauses
    segments, _ = stt._whisper().transcribe(io.BytesIO(data), vad_filter=True, word_timestamps=True)
    records, words, start, end = [], [], None, None
    for seg in segments:
        if start is None:
            start = getattr(seg, "start", None)
        words.append(seg.text.strip())
        end = getattr(seg, "end", None)
        if sum(len(w) for w in words) > PARAGRAPH_CHARS:
            records.append((" ".join(words), start, end))
            words, start = [], None
    if words:
        records.append((" ".join(words), start, end))
    out = []
    for text, start, end in records:
        if not text.strip():
            continue
        record = {"text": text, "date": "unknown", "char_count": len(text), "word_count": len(text.split()),
                  "original_kind": "audio"}
        if start is not None:  # without times the recording can still be played from the start
            record.update(audio_start=round(float(start), 1), audio_end=round(float(end if end is not None else start), 1))
        out.append(record)
    return out


def ocr_engine() -> str | None:
    """"tesseract", "rapidocr" or None (no local text recognition installed).
    Only looks: importing RapidOCR loads OpenCV, which _rapidocr does in order."""
    from importlib.util import find_spec

    if find_spec("pytesseract") and _tesseract_cmd():
        return "tesseract"
    return "rapidocr" if find_spec("rapidocr_onnxruntime") else None


def _tesseract_cmd() -> str | None:
    found = shutil.which("tesseract")
    return found or (str(_WINDOWS_TESSERACT) if _WINDOWS_TESSERACT.is_file() else None)


def _tesseract():
    import os

    import pytesseract

    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
    if (TESSDATA_DIR / "eng.traineddata").is_file():
        # an environment variable, not --tessdata-dir: pytesseract splits its
        # config on spaces, which breaks paths like ".../CHRONUS DB/..."
        os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)
    return pytesseract


@lru_cache(maxsize=1)
def _rapidocr():
    # On Windows, native libraries loaded by OpenCV/onnxruntime before torch's
    # once broke the later loading of torch and the voice models ("DLL load
    # failed"). The server normally loads torch at startup; make that order
    # certain when a photo is read first.
    try:
        import pyarrow.dataset  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        pass
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def _paragraphs(lines: list[tuple[float, float, str]]) -> list[str]:
    """(top, height, text) lines in reading order, joined into paragraphs at larger gaps."""
    lines = sorted(lines)
    if not lines:
        return []
    heights = sorted(h for _, h, _ in lines)
    typical = heights[len(heights) // 2] or 1.0
    paragraphs, current, last_bottom = [], [], None
    for top, height, text in lines:
        if current and last_bottom is not None and top - last_bottom > 0.9 * typical:
            paragraphs.append(" ".join(current))
            current = []
        current.append(text.strip())
        last_bottom = top + height
    paragraphs.append(" ".join(current))
    return [p for p in paragraphs if p.strip()]


def ocr_image_text(image) -> list[str]:
    """Paragraphs of text in a PIL image."""
    engine = ocr_engine()
    if engine is None:
        raise ValueError("Photos and scans need local text recognition: pip install rapidocr-onnxruntime")
    if engine == "tesseract":
        pytesseract = _tesseract()
        langs = [lang for lang in ("eng", "hin", "guj") if lang in pytesseract.get_languages(config="")]
        text = pytesseract.image_to_string(image, lang="+".join(langs) or "eng")
        return [p.strip().replace("\n", " ") for p in text.split("\n\n") if p.strip()]
    import numpy as np

    result, _ = _rapidocr()(np.array(image.convert("RGB")))
    lines = []
    for box, text, score in result or []:
        if float(score) < 0.5:
            continue
        ys = [point[1] for point in box]
        lines.append((min(ys), max(ys) - min(ys), text))
    return _paragraphs(lines)


def _records(paragraphs: list[str], kind: str, page: int | None = None) -> list[dict]:
    out = []
    for text in paragraphs:
        record = {"text": text, "date": "unknown", "char_count": len(text), "word_count": len(text.split()),
                  "original_kind": kind}
        if page is not None:
            record["page"] = page
        out.append(record)
    return out


def read_image(data: bytes) -> list[dict]:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        return _records(ocr_image_text(image), "image")


def read_scanned_pdf(path: Path) -> list[dict]:
    """A PDF with no text layer (a scanned letter): each page read with OCR."""
    import pypdfium2

    records = []
    pdf = pypdfium2.PdfDocument(str(path))
    try:
        for number in range(len(pdf)):
            image = pdf[number].render(scale=2).to_pil()
            records += _records(ocr_image_text(image), "scan", page=number + 1)
    finally:
        pdf.close()
    return records


def make_router() -> APIRouter:
    router = APIRouter(prefix="/personas/{persona_id}", tags=["memories"])

    @router.get("/uploads/{filename}/original")
    def original(persona_id: str = PathParam(pattern=ps.PERSONA_ID_PATTERN),
                 filename: str = PathParam(min_length=1, max_length=200)):
        persona = ps.load_persona(persona_id)
        if persona is None or persona["kind"] != "custom":
            raise HTTPException(status_code=404, detail="No such upload")
        if filename not in {u["filename"] for u in persona.get("uploads", [])}:
            raise HTTPException(status_code=404, detail="No such upload")
        folder = (ps.CUSTOM_DIR / persona["id"] / "uploads").resolve()
        path = (folder / filename).resolve()
        if path.parent != folder or not path.is_file():
            raise HTTPException(status_code=404, detail="No such upload")
        return FileResponse(path, media_type=_MEDIA.get(path.suffix.lower(), "application/octet-stream"),
                            headers={"Cache-Control": "private, no-store", "Content-Disposition": "inline"})

    return router
