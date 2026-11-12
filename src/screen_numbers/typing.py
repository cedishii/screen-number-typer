"""Type text into whatever window has focus, optionally clicking a spot first."""

import time

from pynput import keyboard, mouse

_kb = keyboard.Controller()
_mouse = mouse.Controller()

# Pause after each typed character, in seconds (0.200 s = 200 ms).
KEY_DELAY = 0.200


def type_text(text: str, click_at: tuple[int, int] | None = None, enter: bool = False) -> None:
    """Click `click_at` (screen pixels) if given, type `text`, then press Enter if asked."""
    if click_at:
        _mouse.position = click_at
        _mouse.click(mouse.Button.left)
        time.sleep(0.08)
    for ch in text:
        _kb.type(ch)
        time.sleep(KEY_DELAY)
    if enter:
        time.sleep(0.03)
        _kb.press(keyboard.Key.enter)
        _kb.release(keyboard.Key.enter)
