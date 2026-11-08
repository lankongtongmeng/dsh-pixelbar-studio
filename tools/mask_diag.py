#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断角色表的底色剔除：打印底色、各格前景占比、并出放大掩码图。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from pixelbar import render as rn  # noqa: E402
from pixelbar import sprite as sp  # noqa: E402

for arg in sys.argv[1:]:
    p = pathlib.Path(arg)
    im = Image.open(p).convert("RGBA")
    print(f"== {p.name} {im.size}")
    # 边框采样出的底色
    bgc = rn.auto_background(im)
    print(f"   auto_background = {bgc}")
    # 几个关键位置的实际像素
    px = im.load()
    for (x, y) in [(0, 0), (5, 5), (40, 60), (70, 5), (75, 60), (100, 60),
                   (im.width - 1, im.height - 1)]:
        print(f"   px({x:3d},{y:3d}) = {px[x, y]}")
    # 不同 tol 下的前景占比
    for tol in (30, 60, 90, 120):
        m = rn.frame_foreground(im, bg="auto", bg_tol=tol)
        on = m.convert("L").histogram()[255]
        print(f"   tol={tol:3d} 前景 {on:6d} / {im.width*im.height} "
              f"= {on/(im.width*im.height):.3f}")
    m = rn.frame_foreground(im, bg="auto", bg_tol=60)
    m.convert("L").resize((im.width * 5, im.height * 5), Image.NEAREST).save(
        p.with_name(p.stem + "_mask.png"))
    print(f"   -> {p.stem}_mask.png")
    # 各格前景数
    grid = sp.slice_sheet(p, bg_tol=60)
    for r, line in enumerate(grid):
        counts = [m.convert("L").histogram()[255] for m in line]
        bbs = [m.getbbox() for m in line]
        print(f"   row{r} px={counts} bbox={bbs}")
