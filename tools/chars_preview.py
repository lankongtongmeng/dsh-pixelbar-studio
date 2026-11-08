#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""预览 chars.py 里的全部动画，每张 18 帧拼图。

用法::  python tools/chars_preview.py [--only cat duo parade]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pixelbar import chars as ch  # noqa: E402
from pixelbar import render as rn  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=list(ch.SCENES))
    ap.add_argument("--frames", type=int, default=18)
    ap.add_argument("--out", default=str(ROOT / "gifs" / "anim_prev"))
    a = ap.parse_args()

    outdir = pathlib.Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for name in a.only:
        try:
            cs = ch.canvases(name, n_frames=a.frames)
        except Exception as e:
            print(f"{name}: 失败 {type(e).__name__} {e}")
            continue
        sheet = rn.contact_sheet(cs, cols=3, scale=1)
        f = outdir / f"{name}.png"
        sheet.save(f)
        print(f"{name:10s} {ch.SCENES[name]['label']:20s} {len(cs)} 帧 -> {f.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
