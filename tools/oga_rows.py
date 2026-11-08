#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预览角色表每一行的行走动画，用来挑"哪一行是侧视"。

用法::

    python tools/oga_rows.py gifs/oga/carrot..png --style hills
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pixelbar import render as rn  # noqa: E402
from pixelbar import sprite as sp  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("--style", default="hills")
    ap.add_argument("--out", default=str(ROOT / "gifs" / "rows"))
    a = ap.parse_args()

    p = pathlib.Path(a.sheet)
    grid = sp.slice_sheet(p)
    outdir = pathlib.Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # 每行取 6 帧（覆盖 3 帧循环两轮）拼一行
    for r, line in enumerate(grid):
        bb = sp.content_bbox(line)
        if bb is None:
            print(f"row {r}: 空")
            continue
        tiles = [m.crop(bb) for m in line]
        canvas = rn.new_canvas()
        x = 8
        for t in tiles:
            canvas = rn.blit(canvas, t, x, 0)
            x += t.width + 10
        # 顺带叠一个真实场景帧
        canvases = sp.walk_canvases(p, row=r, n_frames=6, style=a.style)
        sheet = rn.contact_sheet(canvases, cols=1, scale=2)
        strip = rn.canvas_to_image(canvas, scale=2)
        comb = rn.Image.new("L", (max(sheet.width, strip.width),
                                 sheet.height + strip.height + 4), 0)
        comb.paste(strip, (0, 0))
        comb.paste(sheet, (0, strip.height + 4))
        f = outdir / f"{p.stem[:12]}_row{r}.png"
        comb.save(f)
        print(f"row {r}: bbox={bb} 每帧 {tiles[0].size} -> {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
