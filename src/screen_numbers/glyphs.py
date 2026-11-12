"""Check OCR's digits against saved digit shapes.

Windows OCR misreads some game fonts, e.g. a slashed zero read as 9 or skipped.
The number is cut into one shape per digit, and each shape is compared with the
reference shapes in the `glyphs` folder (files named "<digit>_<anything>.png").
Where a shape clearly matches a reference, that digit wins over OCR's guess.

Teach it a font's digits from a screenshot whose number you know:
    screen-numbers --image shot.png --learn 327300
"""

import hashlib
from pathlib import Path

from PIL import Image

GLYPH_DIR = Path(__file__).with_name("glyphs")
SIZE = (24, 24)        # every shape is scaled to 24 px tall, kept in proportion, centred
MATCH = 0.85           # same digit in the same font scores ~0.9+, others stay well below
MARGIN = 0.04          # the best digit must beat the next-best digit by this much
STRICT = 0.93          # to overrule OCR with a digit that has no saved shape of its own
_templates = None


def _load() -> list[tuple[str, list[int]]]:
    global _templates
    if _templates is None:
        _templates = []
        for f in sorted(GLYPH_DIR.glob("*.png")):
            if f.name[0].isdigit():
                _templates.append((f.name[0], _ink(Image.open(f).convert("L"))))
    return _templates


def _normalize(img: Image.Image) -> Image.Image:
    """Scale to SIZE's height keeping the width in proportion, so a narrow 1
    stays narrow, and centre it on a black SIZE canvas. Older 16x24 reference
    files come through unchanged apart from the padding."""
    W, H = SIZE
    w = max(1, min(W, round(H * img.width / max(img.height, 1))))
    canvas = Image.new("L", SIZE, 0)
    canvas.paste(img.resize((w, H), Image.BILINEAR), ((W - w) // 2, 0))
    return canvas


def _ink(img: Image.Image) -> list[int]:
    return list(_normalize(img).get_flattened_data())


def _similarity(a: list[int], b: list[int]) -> float:
    """Overlap of two grey shapes: 1.0 identical, 0.0 nothing in common."""
    both = sum(min(x, y) for x, y in zip(a, b))
    either = sum(max(x, y) for x, y in zip(a, b))
    return both / either if either else 0.0


def segment(prepared: Image.Image, box) -> list[Image.Image]:
    """One shape per character inside `box` (x, y, w, h) of an image from
    ocr._prepare, where text is always dark on light. Shapes are grey, ink white."""
    x, y, w, h = (int(v) for v in box)
    crop = prepared.crop((x - 4, y - 4, x + w + 4, y + h + 4))
    px = crop.load()
    W, H = crop.size
    values = crop.get_flattened_data()
    lo, hi = min(values), max(values)
    if hi - lo < 40:
        return []
    t = lo + 0.45 * (hi - lo)
    ink = [[px[i, j] < t for j in range(H)] for i in range(W)]
    shapes, start = [], None
    for i in range(W + 1):
        has_ink = i < W and any(ink[i])
        if has_ink and start is None:
            start = i
        elif not has_ink and start is not None:
            rows = [j for j in range(H) if any(ink[c][j] for c in range(start, i))]
            shape = crop.crop((start, rows[0], i, rows[-1] + 1))
            shapes.append(shape.point(lambda v: max(0, min(255, round((hi - v) * 255 / (hi - lo))))))
            start = None
    return shapes


def scores(shape: Image.Image) -> dict[str, float]:
    """Each known digit's best score against `shape`."""
    ink = _ink(shape)
    out = {}
    for digit, ref in _load():
        out[digit] = max(out.get(digit, 0.0), _similarity(ink, ref))
    return out


def best_match(shape: Image.Image) -> tuple[str | None, float]:
    s = scores(shape)
    if not s:
        return None, 0.0
    digit = max(s, key=s.get)
    return digit, s[digit]


def _verdict(s: dict[str, float]) -> tuple[str | None, float]:
    """The digit a shape clearly is, or None. Clear means a good score that
    beats every other digit by MARGIN, so look-alikes (a 9 and a slashed 0)
    don't flip on a near tie."""
    ranked = sorted(s.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < MATCH:
        return None, 0.0
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < MARGIN:
        return None, 0.0
    return ranked[0]


def known_digits() -> set[str]:
    return {d for d, _ in _load()}


def correct(prepared: Image.Image, box, text: str) -> str:
    """OCR's `text` with every digit whose shape clearly matches a reference
    replaced by that reference's digit. Also restores digits OCR skipped.
    "?" in `text` marks a character OCR couldn't read; it stays "?" unless a
    shape fills it in."""
    if not all(c.isdigit() or c == "?" for c in text) or not _load():
        return text
    shapes = segment(prepared, box)
    if not shapes or len(shapes) > 2 * len(text) + 2:
        return text
    known = known_digits()
    sure = []
    for shape in shapes:
        digit, score = _verdict(scores(shape))
        sure.append((digit, score) if digit else None)
    if not any(sure):
        return text

    def agrees(i, c):
        """Shape i and OCR's character c don't contradict each other. A digit
        with no saved shape (say OCR's 9 when only 0 is saved) is only
        overruled by a very close match, since the shape has nothing of its
        own to be compared with."""
        if sure[i] is None or c in (sure[i][0], "?"):
            return True
        return c not in known and sure[i][1] < STRICT

    def pick(i, c):
        return c if sure[i] is None or (c != "?" and agrees(i, c)) else sure[i][0]
    # Line the shapes up with OCR's digits (edit distance), so a skipped or
    # extra digit in OCR's reading doesn't shift everything after it.
    n, m = len(sure), len(text)
    cost = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = i
    for k in range(1, m + 1):
        cost[0][k] = k
    for i in range(1, n + 1):
        for k in range(1, m + 1):
            same = agrees(i - 1, text[k - 1])
            cost[i][k] = min(cost[i - 1][k - 1] + (0 if same else 1),
                             cost[i - 1][k] + 1, cost[i][k - 1] + 1)
    out, i, k = [], n, m
    while i > 0:
        same = k > 0 and agrees(i - 1, text[k - 1])
        if k > 0 and cost[i][k] == cost[i - 1][k - 1] + (0 if same else 1):
            out.append(pick(i - 1, text[k - 1])); i -= 1; k -= 1
        elif cost[i][k] == cost[i - 1][k] + 1:
            if sure[i - 1]:                    # a shape OCR skipped
                out.append(sure[i - 1][0])
            i -= 1
        else:
            k -= 1                             # OCR read a digit with no shape
    return "".join(reversed(out))


def learn(prepared: Image.Image, box, number: str) -> int:
    """Save each digit's shape as a reference. Returns how many were new."""
    shapes = segment(prepared, box)
    if len(shapes) != len(number):
        raise ValueError(f"found {len(shapes)} digit shapes but {number!r} has {len(number)} digits")
    GLYPH_DIR.mkdir(exist_ok=True)
    saved = 0
    for digit, shape in zip(number, shapes):
        known, score = best_match(shape)
        if known == digit and score >= 0.93:
            continue
        img = _normalize(shape)
        name = hashlib.sha1(img.tobytes()).hexdigest()[:8]
        img.save(GLYPH_DIR / f"{digit}_{name}.png")
        _load().append((digit, _ink(img)))
        saved += 1
    return saved
