#!/usr/bin/env python3
"""Generate docs/takoron_cover.png — the colour README cover image.

GitHub renders Markdown images but not the inline-styled cells of
``docs/takoron_preview.html``, so the README needs a real raster image
to show Takoron in colour on the repository front page.

This draws the six life stages from :mod:`opentama.art` (the same
``PALETTE`` + ``GRIDS`` the truecolor terminal renderer uses) straight
to a PNG with Pillow — no browser, so it reproduces in CI on any OS.
Captions use romaji + Pillow's bundled font to stay font-independent.

Usage:
    python scripts/make_cover.py
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

# Allow running from the repo root without installing.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from opentama import art  # noqa: E402

STAGES = ["egg", "baby", "child", "teen", "adult", "elder"]
LABELS = {
    "egg": "EGG",
    "baby": "BABY",
    "child": "CHILD",
    "teen": "TEEN",
    "adult": "ADULT",
    "elder": "ELDER",
}

# Layout (pixels). Mirrors docs/takoron_preview.html's palette/spacing.
SCALE = 12          # px per art pixel
SCREEN_PAD = 12     # black inner screen padding
CARD_PAD = 16       # card padding around the screen
CARD_GAP = 20       # gap between cards
PAGE_PAD = 32       # outer page margin
CAPTION_H = 26      # caption strip height under each screen

BG_PAGE = (13, 17, 23)      # #0d1117
BG_CARD = (22, 27, 34)      # #161b22
BG_SCREEN = (0, 0, 0)       # black LCD
BORDER = (48, 54, 61)       # #30363d
TEXT = (230, 237, 243)      # #e6edf3


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow without sized default
        return ImageFont.load_default()


def _draw_sprite(draw: ImageDraw.ImageDraw, grid: list[str], ox: int, oy: int) -> None:
    """Draw one stage grid; '.' stays transparent (shows the screen)."""
    for ry, row in enumerate(grid):
        for cx, key in enumerate(row):
            if key == ".":
                continue
            colour = art.PALETTE.get(key)
            if colour is None:
                continue
            x0 = ox + cx * SCALE
            y0 = oy + ry * SCALE
            draw.rectangle([x0, y0, x0 + SCALE - 1, y0 + SCALE - 1], fill=colour)


def build_image() -> Image.Image:
    grid_w = len(art.GRIDS[STAGES[0]][0]) * SCALE
    grid_h = len(art.GRIDS[STAGES[0]]) * SCALE
    screen_w = grid_w + SCREEN_PAD * 2
    screen_h = grid_h + SCREEN_PAD * 2
    card_w = screen_w + CARD_PAD * 2
    card_h = screen_h + CARD_PAD * 2 + CAPTION_H

    width = PAGE_PAD * 2 + len(STAGES) * card_w + (len(STAGES) - 1) * CARD_GAP
    height = PAGE_PAD * 2 + card_h

    img = Image.new("RGB", (width, height), BG_PAGE)
    draw = ImageDraw.Draw(img)
    font = _load_font(13)

    x = PAGE_PAD
    y = PAGE_PAD
    for stage in STAGES:
        # Card.
        draw.rounded_rectangle(
            [x, y, x + card_w - 1, y + card_h - 1],
            radius=14, fill=BG_CARD, outline=BORDER, width=1,
        )
        # Black screen.
        sx = x + CARD_PAD
        sy = y + CARD_PAD
        draw.rounded_rectangle(
            [sx, sy, sx + screen_w - 1, sy + screen_h - 1],
            radius=8, fill=BG_SCREEN,
        )
        # Sprite.
        _draw_sprite(draw, art.GRIDS[stage], sx + SCREEN_PAD, sy + SCREEN_PAD)
        # Caption.
        label = LABELS[stage]
        tb = draw.textbbox((0, 0), label, font=font)
        tw = tb[2] - tb[0]
        draw.text(
            (x + (card_w - tw) // 2, sy + screen_h + 6),
            label, fill=TEXT, font=font,
        )
        x += card_w + CARD_GAP

    return img


def main() -> int:
    out = pathlib.Path(__file__).resolve().parents[1] / "docs" / "takoron_cover.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    build_image().save(out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
