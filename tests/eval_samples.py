"""Accuracy check on real game screenshots in tests/samples (named <number>.png).

Each sample is placed in a screen-sized dark area at a few sizes, the way the
app sees it when reading the middle of the screen.

    python tests/eval_samples.py           # with the saved digit shapes
    python tests/eval_samples.py --loo     # leave-one-out: shapes learned from the other samples only
"""
import pathlib
import sys
import tempfile

from PIL import Image

from screen_numbers import glyphs, ocr

SAMPLES = sorted(pathlib.Path(__file__).with_name("samples").glob("*.png"))
SCALES = (1.0, 0.75, 0.6, 0.5)
AREA = (1536, 842)   # the "middle" area of a 1920x1080 screen


def on_screen(img, scale):
    img = img.convert("RGB")
    if scale != 1.0:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    bg = Image.new("RGB", AREA, img.getpixel((2, 2)))
    bg.paste(img, ((AREA[0] - img.width) // 2, (AREA[1] - img.height) // 2))
    return bg


def use_shapes_from(samples):
    glyphs.GLYPH_DIR = pathlib.Path(tempfile.mkdtemp())
    glyphs._templates = []
    for f in samples:
        ocr.learn_main_number(Image.open(f), f.stem)


def main():
    loo = "--loo" in sys.argv
    ok = total = raw_ok = 0
    for f in SAMPLES:
        if loo:
            use_shapes_from([s for s in SAMPLES if s != f])
        for scale in SCALES:
            img = on_screen(Image.open(f), scale)
            cands = ocr._number_candidates(img)[1]
            raw = cands[0][0] if cands else None
            got = ocr.read_main_number(img)
            total += 1; ok += got == f.stem; raw_ok += raw == f.stem
            if got != f.stem or raw != f.stem:
                print(f"{f.stem:>8} x{scale:<4}  OCR alone: {raw}  final: {got}  {'OK' if got == f.stem else 'WRONG'}")
    print(f"OCR alone {raw_ok}/{total}, with digit shapes {ok}/{total}")


if __name__ == "__main__":
    main()
