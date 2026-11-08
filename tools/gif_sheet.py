#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 rank.json 里的候选渲染成带编号的拼图，供肉眼筛选。

每格 = 一个候选的一帧 256x32 画布（默认取循环中点帧、原地居中），
左上角用 5x7 点阵写上候选编号，便于对照 rank.json。

用法::

    python tools/gif_sheet.py --top 240 --per 24 --scale 2
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from pixelbar import render as rn  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RANK = ROOT / "gifs" / "rank.json"
OUT = ROOT / "gifs" / "montage"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank", default=str(RANK))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--tag", default="", help="输出文件名前缀")
    ap.add_argument("--top", type=int, default=240)
    ap.add_argument("--per", type=int, default=24, help="每张拼图放几个")
    ap.add_argument("--cols", type=int, default=2)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--mode", choices=["sprite", "scene"], default="sprite")
    a = ap.parse_args()

    rows = json.loads(pathlib.Path(a.rank).read_text(encoding="utf-8"))
    rows = rows[:a.top]
    outdir = pathlib.Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)

    cw, chh = rn.WIDTH + 6, rn.HEIGHT + 6
    per_page = a.per
    for page in range((len(rows) + per_page - 1) // per_page):
        chunk = rows[page * per_page:(page + 1) * per_page]
        nrow = (len(chunk) + a.cols - 1) // a.cols
        sheet = Image.new("L", (cw * a.cols, chh * nrow), 40)
        for k, r in enumerate(chunk):
            gi = page * per_page + k
            p = ROOT / r["path"]
            try:
                if a.mode == "scene":
                    frames = rn.gif_frames(p, max_frames=6, mode="scene", fit="height")
                else:
                    frames = rn.gif_frames(p, max_frames=6, target_h=28,
                                           travel=False, ground=None)
                mid = frames[len(frames) // 2]
                img = rn.canvas_to_image(mid)
            except Exception as e:
                img = Image.new("L", (rn.WIDTH, rn.HEIGHT), 0)
                print(f"  [{gi}] 渲染失败 {p.name}: {type(e).__name__} {e}")
            rr, cc = divmod(k, a.cols)
            x0, y0 = cc * cw + 3, rr * chh + 3
            sheet.paste(img, (x0, y0))
            d = ImageDraw.Draw(sheet)
            d.text((x0 + 2, y0 + 1), f"#{gi}", fill=160)
        if a.scale > 1:
            sheet = sheet.resize((sheet.width * a.scale, sheet.height * a.scale),
                                 Image.NEAREST)
        out = outdir / f"{a.tag}{a.mode}_{page:02d}.png"
        sheet.save(out)
        print(f"  {out}  ({len(chunk)} 个)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
