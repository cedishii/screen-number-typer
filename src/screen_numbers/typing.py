"""Type text into whatever window has focus, optionally clicking a spot first."""

import time

from pynput import keyboard, mouse

_kb = keyboard.Controller()
_mouse = mouse.Controller()


def type_text(text: str, click_at: tuple[int, int] | None = None, enter: bool = False) -> None:
    """Click `click_at` (screen pixels) if given, type `text`, then press Enter if asked."""
    if click_at:
        _mouse.position = click_at
        _mouse.click(mouse.Button.left)
        time.sleep(0.08)
    _kb.type(text)
    if enter:
        time.sleep(0.03)
        _kb.press(keyboard.Key.enter)
        _kb.release(keyboard.Key.enter)
