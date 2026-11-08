#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精灵表切片：把 PNG 里的角色格子按连通域切出来，供合成动画。

Pepper&Carrot 的 24x32 角色表结构：左侧 3 列 x 4 行角色格子（每行一个朝向，
每列一个行走帧），右侧是人像大图。用 alpha 连通域 + 尺寸过滤即可分离。

用法::

    python tools/sprite_sheet.py gifs/oga/Pepper_publish..png            # 打印格子
    python tools/sprite_sheet.py --sheet gifs/oga/carrot..png --zoom     # 出放大图
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from collections import deque

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402


def components(mask, min_px: int = 12):
    """alpha 掩码 -> 连通域包围盒列表（8 邻接）。"""
    w, h = mask.size
    px = mask.load()
    seen = [[False] * w for _ in range(h)]
    out = []
    for sy in range(h):
        for sx in range(w):
            if seen[sy][sx] or px[sx, sy] == 0:
                continue
            q = deque([(sx, sy)])
            seen[sy][sx] = True
            x0 = x1 = sx
            y0 = y1 = sy
            n = 0
            while q:
                x, y = q.popleft()
                n += 1
                x0, x1 = min(x0, x), max(x1, x)
                y0, y1 = min(y0, y), max(y1, y)
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < w and 0 <= yy < h and not seen[yy][xx] \
                                and px[xx, yy]:
                            seen[yy][xx] = True
                            q.append((xx, yy))
            if n >= min_px:
                out.append((x0, y0, x1 + 1, y1 + 1, n))
    return out


def load_alpha(path):
    """返回 (RGBA 图, 前景掩码)。表底色是实色青绿，故用底色剔除而非 alpha。"""
    from pixelbar import render as rn
    im = Image.open(path).convert("RGBA")
    if rn.has_transparency(im):
        mask = im.getchannel("A").point(lambda v: 255 if v >= 96 else 0)
    else:
        mask = rn.frame_foreground(im, bg="auto", bg_tol=60).convert("L")
    return im, mask


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sheets", nargs="*")
    ap.add_argument("--min-px", type=int, default=40)
    ap.add_argument("--zoom", action="store_true")
    a = ap.parse_args()

    for s in a.sheets:
        p = pathlib.Path(s)
        im, mask = load_alpha(p)
        comps = components(mask, a.min_px)
        print(f"== {p.name} {im.size} 连通域 {len(comps)}")
        for c in sorted(comps, key=lambda c: (c[1] // 16, c[0])):
            print(f"   bbox=({c[0]:3d},{c[1]:3d})-({c[2]:3d},{c[3]:3d}) "
                  f"size={c[2]-c[0]:3d}x{c[3]-c[1]:3d} px={c[4]}")
        if a.zoom:
            # 画出连通域框，放大看
            from PIL import ImageDraw
            vis = im.copy()
            d = ImageDraw.Draw(vis)
            for c in comps:
                d.rectangle([c[0], c[1], c[2] - 1, c[3] - 1], outline=(255, 0, 0, 255))
            bg = Image.new("RGBA", vis.size, (24, 24, 40, 255))
            bg.alpha_composite(vis)
            sc = 6
            bg.convert("RGB").resize((vis.width * sc, vis.height * sc),
                                     Image.NEAREST).save(
                p.with_name(p.stem + "_boxes.png"))
            print(f"   -> {p.stem}_boxes.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
