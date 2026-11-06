#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the Neos75 assistant icon set.

Design: dark rounded tile (app palette #0D1016), a glowing accent-blue screen
panel with an activity dot, and a keyboard base bar with key dots below —
readable from 16px taskbar size up to 256px.
"""
from PIL import Image, ImageDraw

ACCENT = (77, 107, 254)        # #4D6BFE
ACCENT_HI = (124, 150, 255)
BG = (13, 16, 22)              # #0D1016
FG = (242, 244, 248)
MINT = (0, 214, 164)

S = 256


def rounded(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_icon(size, running=True):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = 10
    # tile
    rounded(d, (pad, pad, S - pad, S - pad), 52, fill=BG + (255,),
            outline=(38, 46, 62, 255), width=4)

    # screen panel (upper 55%)
    sx0, sy0, sx1, sy1 = 46, 44, S - 46, 142
    rounded(d, (sx0, sy0, sx1, sy1), 20, fill=(24, 30, 42, 255),
            outline=ACCENT + (255,), width=6)
    # screen content: activity bars (brighter when running)
    bars = [0.35, 0.6, 0.85, 0.5, 0.7]
    bw = (sx1 - sx0 - 48) // len(bars)
    for i, frac in enumerate(bars):
        h = int((sy1 - sy0 - 44) * (frac if running else 0.28))
        x = sx0 + 24 + i * bw
        col = (ACCENT_HI if i % 2 else ACCENT) if running else (86, 96, 116)
        d.rounded_rectangle((x, sy1 - 20 - h, x + bw - 12, sy1 - 20),
                            radius=6, fill=col + (255,))
    # status dot top-right of the screen
    dot = MINT if running else (110, 118, 132)
    d.ellipse((sx1 - 40, sy0 + 12, sx1 - 20, sy0 + 32), fill=dot + (255,))

    # keyboard base
    ky0, ky1 = 168, 212
    rounded(d, (sx0, ky0, sx1, ky1), 16, fill=(30, 36, 50, 255),
            outline=(58, 66, 86, 255), width=4)
    kw_ = (sx1 - sx0 - 36) / 5
    for i in range(5):
        x = sx0 + 18 + i * kw_
        d.rounded_rectangle((x, ky0 + 12, x + kw_ - 14, ky1 - 12),
                            radius=6, fill=(70, 80, 102, 255))

    if size != S:
        img = img.resize((size, size), Image.LANCZOS)
    return img


if __name__ == "__main__":
    from pathlib import Path
    out = Path(__file__).resolve().parents[1] / "Neos75Lyrics-" / "assets"
    out.mkdir(exist_ok=True)

    main_run = draw_icon(S, True)
    main_stop = draw_icon(S, False)

    main_run.save(out / "app-icon.png")                 # 256 png (tray/sidebar)
    main_run.resize((64, 64), Image.LANCZOS).save(out / "app-icon-64.png")

    # multi-size ICO for window/taskbar
    ico_sizes = [256, 128, 64, 48, 32, 24, 16]
    main_run.save(out / "app-icon.ico",
                  format="ICO",
                  sizes=[(s, s) for s in ico_sizes])

    main_stop.save(out / "app-icon-stop.png")           # tray "stopped" state
    print("icons written:", sorted(p.name for p in out.glob("app-icon*")))
