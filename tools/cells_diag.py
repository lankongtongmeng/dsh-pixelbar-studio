#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查切片结果：每格前景像素数与包围盒，并出放大掩码图。"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from pixelbar import sprite as sp  # noqa: E402

for arg in sys.argv[1:]:
    p = pathlib.Path(arg)
    grid = sp.slice_sheet(p)
    print(f"== {p.name}")
    for r, line in enumerate(grid):
        counts = [m.convert("L").histogram()[255] for m in line]
        bbs = [m.getbbox() for m in line]
        print(f"   row{r} px={counts}")
        print(f"        bbox={bbs}")
    # 放大整块掩码
    sheet = Image.new("1", (sp.COLS * sp.CELL_W, sp.ROWS * sp.CELL_H), 0)
    for r, line in enumerate(grid):
        for c, m in enumerate(line):
            sheet.paste(m, (c * sp.CELL_W, r * sp.CELL_H))
    sheet.convert("L").resize((sheet.width * 5, sheet.height * 5),
                              Image.NEAREST).save(p.with_name(p.stem + "_cells.png"))
    print(f"   -> {p.stem}_cells.png")
