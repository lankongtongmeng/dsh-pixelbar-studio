#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验导出的 GIF：尺寸、帧数、循环标记、帧间隔。"""
from __future__ import annotations

import pathlib
import sys

from PIL import Image

for arg in sys.argv[1:] or ["gifs/anime"]:
    p = pathlib.Path(arg)
    files = sorted(p.glob("*.gif")) if p.is_dir() else [p]
    for f in files:
        with Image.open(f) as im:
            n = getattr(im, "n_frames", 1)
            print(f"{f.name:14s} {im.size[0]}x{im.size[1]} frames={n:3d} "
                  f"mode={im.mode} loop={im.info.get('loop')} "
                  f"dur={im.info.get('duration')} {f.stat().st_size:>7d} B")
