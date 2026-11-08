#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量渲染 5 个 Pepper&Carrot 角色的行走动画预览（每行一个朝向）。

用法::

    python tools/chars.py                      # 全部角色、全部行
    python tools/chars.py --only carrot        # 只做某个
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pixelbar import render as rn  # noqa: E402
from pixelbar import sprite as sp  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OGA = ROOT / "gifs" / "oga"

SHEETS = {
    "pepper": "Pepper_publish..png",
    "carrot": "carrot..png",
    "coriander": "coriander_publish..png",
    "saffron": "saffron_publish..png",
    "shichimi": "shichimi_publish..png",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=list(SHEETS))
    ap.add_argument("--style", default="ground")
    ap.add_argument("--frames", type=int, default=20)
    ap.add_argument("--out", default=str(ROOT / "gifs" / "chars"))
    a = ap.parse_args()

    outdir = pathlib.Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for name in a.only:
        p = OGA / SHEETS[name]
        if not p.exists():
            print(f"{name}: 缺文件 {p}")
            continue
        grid = sp.slice_sheet(p)
        # 每行各出一张预览，方便挑朝向
        tiles = []
        for r in range(sp.ROWS):
            bb = sp.content_bbox(grid[r])
            tag = "空" if bb is None else f"{bb[2]-bb[0]}x{bb[3]-bb[1]}"
            print(f"{name} row{r}: {tag}")
            if bb is None:
                continue
            canvases = sp.walk_canvases(grid, row=r, n_frames=a.frames,
                                        style=a.style)
            sheet = rn.contact_sheet(canvases, cols=4, scale=2)
            f = outdir / f"{name}_row{r}.png"
            sheet.save(f)
            tiles.append(f)
        print(f"  -> {len(tiles)} 张预览在 {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
