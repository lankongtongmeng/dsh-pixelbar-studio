#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把精灵表放大若干倍输出，便于看清格子布局。"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

for arg in sys.argv[1:]:
    p = pathlib.Path(arg)
    with Image.open(p) as im:
        print(f"{p.name}: {im.size} mode={im.mode} frames={getattr(im,'n_frames',1)}")
        out = p.with_name(p.stem + "_x6.png")
        scale = 6
        im2 = im.convert("RGBA")
        bg = Image.new("RGBA", im2.size, (24, 24, 40, 255))
        bg.alpha_composite(im2)
        bg = bg.convert("RGB").resize((im2.width * scale, im2.height * scale),
                                      Image.NEAREST)
        bg.save(out)
        print(f"  -> {out}")
