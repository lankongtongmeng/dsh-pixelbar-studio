#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 anims 的 5 个动画各取 6 帧，纵向拼成一张总览图（供肉眼核对设备内容）。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from pixelbar import chars as ch  # noqa: E402
from pixelbar import render as rn  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOW = 6


def _font(size: int = 13):
    """标签要显示中文，必须用宋体；PIL 默认位图字体不含中文字形（会出方块）。"""
    try:
        return ImageFont.truetype(rn.CJK_FONT, size)
    except Exception:
        return ImageFont.load_default()


def main() -> int:
    rows = []
    for name, cat in ch.DEFAULT_SLOTS.items():
        cs = ch.canvases(name)
        idx = [round(i * (len(cs) - 1) / (SHOW - 1)) for i in range(SHOW)]
        rows.append((name, cat, [cs[i] for i in idx]))

    pad, label_h = 4, 18
    w = rn.WIDTH * SHOW + pad * (SHOW + 1)
    h = (rn.HEIGHT + label_h) * len(rows) + pad
    sheet = Image.new("L", (w, h), 30)
    d = ImageDraw.Draw(sheet)
    font = _font()
    for r, (name, cat, frames) in enumerate(rows):
        y = pad + r * (rn.HEIGHT + label_h)
        d.text((pad, y + 2),
               f"{name}  ->  category {cat}    {ch.SCENES[name]['label']}",
               fill=210, font=font)
        for c, cv in enumerate(frames):
            x = pad + c * (rn.WIDTH + pad)
            sheet.paste(rn.canvas_to_image(cv), (x, y + label_h))
    sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
    out = ROOT / "gifs" / "anims_overview.png"
    sheet.save(out)
    print(f"{out}  ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
