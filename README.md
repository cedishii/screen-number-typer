# screen-numbers

Reads numbers off the screen on Windows. It screenshots the middle of the screen, finds the main number (the biggest one, preferring the centre) and can type it into an answer box.

It uses the text recognition built into Windows (`Windows.Media.Ocr`), so nothing is sent online and there is no model to download.

Use it three ways:

1. **From Python**: `import screen_numbers`
2. **From any other app**: run the `screen-numbers` command and read what it prints
3. **As a desktop tool**: `app.py`, a small window with an F8 hotkey

## Install

Needs Windows 10 or 11 and Python 3.10 or newer.

```
pip install git+https://github.com/cedishii/screen-number-typer.git
```

Or from a local copy, in your other app's environment:

```
pip install -e "C:\Github Projects\screen-number-typer"
```

## 1. From Python

```python
from screen_numbers import read_number, read_numbers, read_text, type_text

read_number()                              # "33333333", main number in the middle of the screen
read_number(region="middle-small")         # just the centre ("middle-medium" sits between)
read_number(region="screen")               # anywhere on screen
read_number(region=(100, 200, 600, 400))   # inside a box: left, top, right, bottom (screen pixels)
read_number(image=pil_image)               # in a picture you already have

read_numbers()   # every number: [{"kind": "date", "text": "11/11/2026"}, {"kind": "number", "text": "52"}]
read_text()      # all the text it sees

type_text("33333333", click_at=(900, 700), enter=True)   # click the answer box, type, press Enter
```

`read_number` returns a string, or `None` when there is no number. Strings keep leading zeros and date or time formatting (`"007"`, `"2:37 PM"`).

Other helpers: `capture(region)` returns the screenshot as a PIL image, `middle_box()` returns the middle area's coordinates, and `MIDDLE` holds the fractions it uses: `(0.10, 0.10, 0.90, 0.88)`.

## 2. From any other app

```
screen-numbers                         prints the main number, e.g. 33333333
screen-numbers --region middle-small   look only at the centre (or middle-medium)
screen-numbers --region screen         look anywhere on screen
screen-numbers --box 100 200 600 400   look inside a box
screen-numbers --image shot.png        read a picture file
screen-numbers --all --json            every number as JSON
screen-numbers --json                  {"number": "33333333"}
screen-numbers --type --enter          also type it into the focused window, then press Enter
screen-numbers --type --click 900 700  click there first, then type
```

Exit code: `0` a number was found, `1` none found, `2` error (the message goes to stderr).

Example from Node.js:

```js
const { execFileSync } = require("child_process");
const { number } = JSON.parse(execFileSync("screen-numbers", ["--json"]).toString());
```

## 3. Desktop tool

Double-click `run.bat`. The first run creates `.venv` and installs everything.

- **Read (F8)** reads the middle of the screen and shows the number. F8 works while other windows are in front.
- **Middle size** picks how much of the middle to read: Large (default), Medium or Small.
- **Select area** reads only a box you drag. **Use middle** goes back.
- **Keep watching** reads every second and reacts when the number changes.
- **Type after reading** types the number, optionally clicking an answer box first and pressing Enter.

Settings are saved in `settings.json`.

## How it reads

Small text is enlarged and light-on-dark text is inverted before reading. Letters that look like digits (O→0, l→1, S→5) are corrected only inside words that are mostly digits. The main number is the one with the tallest text, with a tie-break towards the centre.
