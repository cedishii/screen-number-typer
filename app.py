"""Screen Number Reader: screenshot the screen, find the main number, optionally type it."""

import json
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import mss
from PIL import Image, ImageTk
from pynput import keyboard

import screen_numbers  # also makes this process DPI aware, so dragged areas match captures

SETTINGS = Path(__file__).with_name("settings.json")
HOTKEY = "<f8>"


def load_settings():
    try:
        return json.loads(SETTINGS.read_text())
    except Exception:
        return {}


def grab(box=None):
    """Screenshot a box (left, top, right, bottom), or the whole desktop when box is None."""
    with mss.mss() as sct:
        mon = sct.monitors[0]
        area = box and {"left": box[0], "top": box[1], "width": box[2] - box[0], "height": box[3] - box[1]}
        shot = sct.grab(area or mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return img, (mon["left"], mon["top"]) if not area else (box[0], box[1])


class Picker(tk.Toplevel):
    """A frozen, dimmed screenshot of the desktop. Drag a box, or click once for a point."""

    def __init__(self, root, mode, on_done):
        super().__init__(root)
        self.mode, self.on_done = mode, on_done
        img, (self.ox, self.oy) = grab()
        dim = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.45)
        self.photo = ImageTk.PhotoImage(dim)
        self.bright = img
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{img.width}x{img.height}+{self.ox}+{self.oy}")
        self.canvas = tk.Canvas(self, width=img.width, height=img.height, highlightthickness=0, cursor="crosshair")
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        tip = "Drag a box around the number" if mode == "area" else "Click the answer box"
        self.canvas.create_text(img.width // 2 - self.ox, 40 - self.oy, text=tip + "   (Esc to cancel)",
                                fill="white", font=("Segoe UI", 16, "bold"))
        self.start = self.rect = self.peek = None
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.bind("<Escape>", lambda e: self.finish(None))
        self.focus_force()

    def press(self, e):
        self.start = (e.x, e.y)
        if self.mode == "point":
            self.finish((e.x + self.ox, e.y + self.oy))

    def drag(self, e):
        if self.mode != "area" or not self.start:
            return
        x0, y0 = self.start
        box = (min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y))
        if box[2] - box[0] < 2 or box[3] - box[1] < 2:
            return
        self.peek_photo = ImageTk.PhotoImage(self.bright.crop(box))
        if self.peek:
            self.canvas.delete(self.peek)
            self.canvas.delete(self.rect)
        self.peek = self.canvas.create_image(box[0], box[1], image=self.peek_photo, anchor="nw")
        self.rect = self.canvas.create_rectangle(*box, outline="#f2b705", width=2)

    def release(self, e):
        if self.mode != "area" or not self.start:
            return
        x0, y0 = self.start
        box = (min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y))
        if box[2] - box[0] < 5 or box[3] - box[1] < 5:
            self.start = None
            return
        self.finish((box[0] + self.ox, box[1] + self.oy, box[2] + self.ox, box[3] + self.oy))

    def finish(self, value):
        self.destroy()
        self.on_done(value)


class App:
    def __init__(self, root):
        self.root = root
        self.s = load_settings()
        self.area = tuple(self.s["area"]) if self.s.get("area") else None
        self.point = tuple(self.s["point"]) if self.s.get("point") else None
        self.busy = False
        self.watching = False
        self.last = None

        root.title("Screen Number Reader")
        root.attributes("-topmost", True)
        root.minsize(360, 0)

        top = ttk.Frame(root)
        top.pack(fill="x", padx=12, pady=(12, 4))
        self.read_btn = ttk.Button(top, text="Read  (F8)", command=self.read)
        self.read_btn.pack(side="left")
        self.watch_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Keep watching", variable=self.watch_var, command=self.toggle_watch).pack(side="left", padx=10)

        self.number_var = tk.StringVar(value="–")
        num = tk.Label(root, textvariable=self.number_var, font=("Segoe UI", 34, "bold"), anchor="center")
        num.pack(fill="x", padx=12, pady=(8, 0))
        row = ttk.Frame(root)
        row.pack(pady=(0, 6))
        ttk.Button(row, text="Copy", command=self.copy).pack(side="left")

        where = ttk.Frame(root)
        where.pack(fill="x", padx=12, pady=4)
        self.area_lbl = ttk.Label(where, foreground="#666")
        self.area_lbl.pack(side="left")
        self.clear_btn = ttk.Button(where, text="Use middle", command=self.clear_area)
        self.clear_btn.pack(side="right")
        ttk.Button(where, text="Select area", command=lambda: self.pick("area")).pack(side="right", padx=6)

        size_row = ttk.Frame(root)
        size_row.pack(fill="x", padx=12, pady=(0, 4))
        ttk.Label(size_row, text="Middle size:").pack(side="left")
        self.size_var = tk.StringVar(value=self.s.get("size", "Large"))
        size_box = ttk.Combobox(size_row, textvariable=self.size_var, values=["Large", "Medium", "Small"],
                                state="readonly", width=8)
        size_box.pack(side="left", padx=6)
        size_box.bind("<<ComboboxSelected>>", lambda e: (self.clear_area(), self.say(f"Middle size: {self.size_var.get()}.")))

        typing = ttk.LabelFrame(root, text="Type the answer (optional)")
        typing.pack(fill="x", padx=12, pady=10)
        self.type_var = tk.BooleanVar(value=self.s.get("type", False))
        self.enter_var = tk.BooleanVar(value=self.s.get("enter", True))
        r1 = ttk.Frame(typing)
        r1.pack(fill="x", padx=8, pady=4)
        ttk.Checkbutton(r1, text="Type after reading", variable=self.type_var, command=self.save).pack(side="left")
        ttk.Checkbutton(r1, text="Press Enter", variable=self.enter_var, command=self.save).pack(side="left", padx=10)
        r2 = ttk.Frame(typing)
        r2.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Button(r2, text="Set answer box", command=lambda: self.pick("point")).pack(side="left")
        self.point_lbl = ttk.Label(r2, foreground="#666")
        self.point_lbl.pack(side="left", padx=8)

        self.status = ttk.Label(root, foreground="#666")
        self.status.pack(anchor="w", padx=12, pady=(0, 10))
        self.refresh_labels()
        self.say("Press Read or F8. It finds the biggest number in the middle of the screen.")

        self.hotkeys = keyboard.GlobalHotKeys({HOTKEY: lambda: root.after(0, self.read)})
        self.hotkeys.start()
        root.protocol("WM_DELETE_WINDOW", self.quit)

    # --- helpers ---
    def say(self, text):
        self.status.config(text=text)

    def save(self):
        self.s.update(area=self.area, point=self.point, type=self.type_var.get(), enter=self.enter_var.get(),
                      size=self.size_var.get())
        try:
            SETTINGS.write_text(json.dumps(self.s, indent=2))
        except OSError:
            pass

    def refresh_labels(self):
        a = self.area
        self.area_lbl.config(text=f"Reading: your area {a[2]-a[0]}×{a[3]-a[1]}" if a
                             else f"Reading: middle of screen ({self.size_var.get()})")
        self.clear_btn.state(["!disabled"] if a else ["disabled"])
        self.point_lbl.config(text=f"Clicks at ({self.point[0]}, {self.point[1]})" if self.point
                              else "Not set: types into whatever window has focus")

    def copy(self):
        value = self.number_var.get()
        if value and value != "–":
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.say(f"Copied {value}")

    def clear_area(self):
        self.area = None
        self.last = None
        self.refresh_labels()
        self.save()

    def pick(self, mode):
        self.root.withdraw()
        self.root.after(250, lambda: Picker(self.root, mode, lambda v: self.picked(mode, v)))

    def picked(self, mode, value):
        self.root.deiconify()
        if value is None:
            self.say("Cancelled.")
            return
        if mode == "area":
            self.area = value
            self.last = None
            self.read()
        else:
            self.point = value
            self.say("Answer box set.")
        self.refresh_labels()
        self.save()

    # --- reading ---
    def read(self, from_watch=False):
        if self.busy:
            return
        self.busy = True
        if not from_watch:
            self.say("Reading...")
        # Step out of the way so this window isn't in the screenshot.
        hide = self.area is None
        if hide:
            self.root.withdraw()
        self.root.after(120 if hide else 0, lambda: threading.Thread(
            target=self._read_worker, args=(from_watch, hide), daemon=True).start())

    def _read_worker(self, from_watch, hidden):
        try:
            size = self.size_var.get().lower()
            region = self.area or ("middle" if size == "large" else f"middle-{size}")
            result = (screen_numbers.read_number(region), None)
        except Exception as e:
            result = (None, str(e))
        self.root.after(0, lambda: self._show(*result, from_watch, hidden))

    def _show(self, number, error, from_watch, hidden):
        self.busy = False
        if hidden:
            self.root.deiconify()
        if error:
            self.say(f"Couldn't read the screen: {error}")
            return
        changed = number != self.last
        self.last = number
        if from_watch and not changed:
            return
        self.number_var.set(number or "–")
        stamp = time.strftime("%H:%M:%S")
        if not number:
            self.say(f"Read at {stamp}: no number found.")
            return
        self.say(f"Read at {stamp}.")
        if self.type_var.get():
            self.root.after(50, lambda: self.type_answer(number))

    def type_answer(self, answer):
        screen_numbers.type_text(answer, click_at=self.point, enter=self.enter_var.get())
        self.say(f"Typed {answer}" + (" and pressed Enter." if self.enter_var.get() else "."))

    # --- watching ---
    def toggle_watch(self):
        self.watching = self.watch_var.get()
        if self.watching:
            if self.area is None:
                self.say("Watching works best with an area selected, so the window doesn't flicker.")
            else:
                self.say("Watching. It reads again whenever the number changes.")
            self.tick()

    def tick(self):
        if not self.watching:
            return
        self.read(from_watch=True)
        self.root.after(1000, self.tick)

    def quit(self):
        self.watching = False
        self.hotkeys.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
