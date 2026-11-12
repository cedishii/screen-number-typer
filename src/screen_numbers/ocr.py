"""Read the text in a picture with Windows' built-in OCR, then pick out the numbers."""

import asyncio
import io
import re

from PIL import Image, ImageOps
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = OcrEngine.try_create_from_user_profile_languages()
        if _engine is None:
            raise RuntimeError(
                "Windows text recognition isn't available. Add a language with OCR in "
                "Settings > Time & language > Language & region."
            )
    return _engine


def _prepare(img: Image.Image) -> Image.Image:
    """Grey, padded and big enough: OCR misses small or edge-hugging text."""
    img = img.convert("L")
    if img.height < 120:
        scale = max(2, round(120 / max(img.height, 1)))
        img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    limit = OcrEngine.max_image_dimension
    if max(img.size) > limit:
        img.thumbnail((limit - 40, limit - 40))
    # Light text on a dark background reads better inverted.
    if sum(img.getdata()) / (img.width * img.height) < 110:
        img = ImageOps.invert(img)
    return ImageOps.expand(img, border=20, fill=255)


async def _recognize(img: Image.Image) -> str:
    return "\n".join(line["text"] for line in await _recognize_lines(img))


async def _recognize_lines(img: Image.Image) -> list[dict]:
    """Each line's text plus its box (x, y, w, h) in the prepared image's pixels."""
    buf = io.BytesIO()
    img.save(buf, "PNG")
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(buf.getvalue())
    await writer.store_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await _get_engine().recognize_async(bitmap)
    lines = []
    for line in result.lines:
        rects = [w.bounding_rect for w in line.words]
        if not rects:
            continue
        x0 = min(r.x for r in rects); y0 = min(r.y for r in rects)
        x1 = max(r.x + r.width for r in rects); y1 = max(r.y + r.height for r in rects)
        lines.append({"text": line.text, "box": (x0, y0, x1 - x0, y1 - y0),
                      "words": [(w.text, r.height) for w, r in zip(line.words, rects)]})
    return lines


def read_text(img: Image.Image) -> str:
    return asyncio.run(_recognize(_prepare(img)))


def read_main_number(img: Image.Image) -> str | None:
    """The most prominent number: the tallest digits, preferring ones near the centre."""
    prepared = _prepare(img)
    lines = asyncio.run(_recognize_lines(prepared))
    cx, cy = prepared.width / 2, prepared.height / 2
    half_diag = (cx ** 2 + cy ** 2) ** 0.5
    best, best_score = None, 0.0
    for line in lines:
        x, y, w, h = line["box"]
        dist = (((x + w / 2) - cx) ** 2 + ((y + h / 2) - cy) ** 2) ** 0.5 / half_diag
        for text, height in _numbers_in(line["words"]):
            score = height * (1 - 0.5 * dist)
            if score > best_score:
                best, best_score = text, score
    return best


MAX_JOINED_DIGITS = 11


def _numbers_in(words: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Number-like words in a line. OCR splits spaced-out digits ("12345 67890")
    into several words, so neighbouring all-digit words of similar height are
    joined back together, up to MAX_JOINED_DIGITS digits."""
    found = []
    run, run_h = "", 0.0
    for word, height in words:
        fixed = fix_lookalikes(word)
        m = re.fullmatch(r"\W*([-+]?\d[\d,./:\-]*\d|\d)\W*", fixed)
        if not m:
            if run:
                found.append((run, run_h))
            run = ""
            continue
        text = m.group(1)
        if (run and text.isdigit() and run.isdigit()
                and len(run) + len(text) <= MAX_JOINED_DIGITS
                and abs(height - run_h) <= 0.25 * max(height, run_h)):
            run, run_h = run + text, max(run_h, height)
            continue
        if run:
            found.append((run, run_h))
        run, run_h = text, height
    if run:
        found.append((run, run_h))
    return found


# Letters OCR often mistakes for digits, fixed only inside number-like words.
_LOOKALIKE = str.maketrans({"O": "0", "o": "0", "D": "0", "I": "1", "l": "1", "|": "1",
                            "Z": "2", "S": "5", "s": "5", "B": "8", "g": "9"})
_WORD = re.compile(r"\S+")

DATE = re.compile(r"\b\d{1,4}([/\-.])\d{1,2}\1\d{2,4}\b")
TIME = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AaPp][Mm])?\b")
NUMBER = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def fix_lookalikes(text: str) -> str:
    def fix(m):
        w = m.group(0)
        digits = sum(c.isdigit() for c in w)
        return w.translate(_LOOKALIKE) if digits and digits >= len(w) / 2 else w
    return _WORD.sub(fix, text)


def find_numbers(text: str) -> list[dict]:
    """Dates and times first, then the remaining plain numbers, in reading order."""
    text = fix_lookalikes(text)
    found, taken = [], []
    for kind, pattern in (("date", DATE), ("time", TIME), ("number", NUMBER)):
        for m in pattern.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append({"kind": kind, "text": m.group(0), "at": m.start()})
    found.sort(key=lambda f: f["at"])
    for f in found:
        del f["at"]
    return found


def all_digits(text: str) -> str:
    return "".join(c for c in fix_lookalikes(text) if c.isdigit())
