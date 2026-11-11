"""Command line, so apps in any language can use it:

    screen-numbers                      prints the main number in the middle of the screen
    screen-numbers --region screen      ...anywhere on screen
    screen-numbers --box 100 200 600 400
    screen-numbers --image shot.png
    screen-numbers --all --json         every number, as JSON
    screen-numbers --type --enter       also type the number into the focused window

Exit code 0 when a number was found, 1 when none, 2 on an error.
"""

import argparse
import json
import sys

from PIL import Image

from . import read_number, read_numbers, type_text


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="screen-numbers", description="Read numbers off the screen.")
    where = p.add_mutually_exclusive_group()
    where.add_argument("--region", choices=["middle", "screen"], default="middle")
    where.add_argument("--box", nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    where.add_argument("--image", help="read this picture file instead of the screen")
    p.add_argument("--all", action="store_true", help="every number, not just the main one")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--type", action="store_true", help="type the main number into the focused window")
    p.add_argument("--enter", action="store_true", help="press Enter after typing")
    p.add_argument("--click", nargs=2, type=int, metavar=("X", "Y"), help="click here before typing")
    a = p.parse_args(argv)

    try:
        region = tuple(a.box) if a.box else a.region
        image = Image.open(a.image) if a.image else None
        if a.all:
            found = read_numbers(region, image)
            print(json.dumps(found) if a.json else "\n".join(n["text"] for n in found))
            return 0 if found else 1
        number = read_number(region, image)
        if a.json:
            print(json.dumps({"number": number}))
        elif number:
            print(number)
        if number and a.type:
            type_text(number, click_at=tuple(a.click) if a.click else None, enter=a.enter)
        return 0 if number else 1
    except Exception as e:
        print(f"screen-numbers: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
