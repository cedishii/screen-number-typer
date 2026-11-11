"""Read numbers off the screen with Windows' built-in OCR.

    from screen_numbers import read_number
    read_number()                          # biggest number in the middle of the screen
    read_number(region="middle-small")     # ...in just the centre ("middle-medium" sits between)
    read_number(region="screen")           # ...anywhere on screen
    read_number(region=(100, 200, 600, 400))  # ...inside a box: left, top, right, bottom
    read_number(image=my_pil_image)        # ...in a picture you already have

Each returns the number as a string ("33333333", "11/11/2026"), or None when there is none.
"""

from PIL import Image

from . import ocr
from .capture import MIDDLE, MIDDLE_SIZES, capture, middle_box, screen_box
from .typing import type_text

__all__ = ["read_number", "read_numbers", "read_text", "capture", "middle_box", "screen_box",
           "type_text", "MIDDLE", "MIDDLE_SIZES"]
__version__ = "0.1.0"


def _image(region, image: Image.Image | None) -> Image.Image:
    return image if image is not None else capture(region)


def read_number(region="middle", image: Image.Image | None = None) -> str | None:
    """The main number: the tallest digits, preferring ones near the centre."""
    return ocr.read_main_number(_image(region, image))


def read_numbers(region="middle", image: Image.Image | None = None) -> list[dict]:
    """Every number, in reading order, as {"kind": "date"|"time"|"number", "text": ...}."""
    return ocr.find_numbers(ocr.read_text(_image(region, image)))


def read_text(region="middle", image: Image.Image | None = None) -> str:
    """All the text OCR sees, one line per line."""
    return ocr.read_text(_image(region, image))
