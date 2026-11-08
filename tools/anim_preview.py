#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量渲染候选 GIF 的横穿动画预览（每帧 256x32，4 列平铺）。

用法::

    python tools/anim_preview.py --out gifs\prev --tag a \
        gifs/gc/XXX.gif gifs/gc/YYY.gif
    python tools/anim_preview.py --rank gifs/rank.json --idx 9 13 15
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pixelbar import render as rn  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def render(path: pathlib.Path, out: pathlib.Path, target_h=28, inplace=False,
           mode="sprite", fit="height", frames=20, ground=28, tag="") -> str:
    try:
        canvases = rn.gif_frames(
            path, max_frames=frames, target_h=target_h, travel=not inplace,
            ground=ground, mode=mode, fit=fit)
    except Exception as e:
        return f"FAIL {path.name}: {type(e).__name__} {e}"
    sheet = rn.contact_sheet(canvases, cols=4, scale=2)
    sheet.save(out)
    return f"OK {path.name} -> {out.name} ({len(canvases)} 帧)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--rank", help="从 rank.json 按下标取文件")
    ap.add_argument("--idx", nargs="*", type=int, default=[])
    ap.add_argument("--out", default=str(ROOT / "gifs" / "prev"))
    ap.add_argument("--tag", default="p")
    ap.add_argument("--inplace", action="store_true")
    ap.add_argument("--no-ground", action="store_true")
    ap.add_argument("--mode", choices=["sprite", "scene"], default="sprite")
    ap.add_argument("--fit", default="height")
    ap.add_argument("--target-h", type=int, default=28)
    ap.add_argument("--frames", type=int, default=20)
    a = ap.parse_args()

    files = [pathlib.Path(f) for f in a.files]
    if a.rank:
        rows = json.loads(pathlib.Path(a.rank).read_text(encoding="utf-8"))
        files += [ROOT / rows[i]["path"] for i in a.idx]
    if not files:
        print("没有输入文件")
        return 1

    outdir = pathlib.Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for k, f in enumerate(files):
        out = outdir / f"{a.tag}_{k:02d}_{f.stem[:8]}.png"
        print(render(f, out, a.target_h, a.inplace, a.mode, a.fit, a.frames,
                     None if a.no_ground else 28))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
