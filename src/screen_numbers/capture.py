"""Screenshots of the screen, a box, or the middle of the main screen."""

import ctypes

import mss
from PIL import Image

# Use real pixels so coordinates match what gets captured on scaled displays.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

# left, top, right, bottom as fractions of the main screen
MIDDLE = (0.10, 0.10, 0.90, 0.88)

Box = tuple[int, int, int, int]  # left, top, right, bottom in screen pixels


def middle_box(fractions: tuple[float, float, float, float] = MIDDLE) -> Box:
    """The middle of the main screen, leaving out the taskbar, title bars and screen edges."""
    with mss.mss() as sct:
        m = sct.monitors[1]
    l, t, r, b = fractions
    return (m["left"] + int(m["width"] * l), m["top"] + int(m["height"] * t),
            m["left"] + int(m["width"] * r), m["top"] + int(m["height"] * b))


def screen_box() -> Box:
    """The whole desktop, across every monitor."""
    with mss.mss() as sct:
        m = sct.monitors[0]
    return (m["left"], m["top"], m["left"] + m["width"], m["top"] + m["height"])


def resolve(region) -> Box:
    """Turn "middle", "screen" or a (left, top, right, bottom) box into a box."""
    if region is None or region == "middle":
        return middle_box()
    if region == "screen":
        return screen_box()
    if isinstance(region, (tuple, list)) and len(region) == 4:
        l, t, r, b = (int(v) for v in region)
        if r - l < 1 or b - t < 1:
            raise ValueError(f"Region {region} is empty: right must be > left and bottom > top.")
        return (l, t, r, b)
    raise ValueError(f'region must be "middle", "screen" or (left, top, right, bottom), not {region!r}')


def capture(region="middle") -> Image.Image:
    """Screenshot a region and return it as a PIL image."""
    l, t, r, b = resolve(region)
    with mss.mss() as sct:
        shot = sct.grab({"left": l, "top": t, "width": r - l, "height": b - t})
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
