#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按精确尺寸从 GifCities 采宽幅素材（8:1 左右，天生贴合 PixelBar）。

GeoCities 时代大量 468x60 / 400x50 的"网页横幅"，宽高比 7.8~8:1，
和 PixelBar 的 256x32 几乎完全一致 —— 这类素材不用裁不用拉伸。

special-search 表单：``q`` + ``width`` + ``height`` + ``page_size`` + ``offset``。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "PixelBar-Research/1.0 (personal hobby use)"}
ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "gifs" / "wide"
INDEX = ROOT / "gifs" / "wide_index.json"

# 宽高比 ~8:1 的常见尺寸；高度留 30~70 保证缩到 32 行时还有细节
SIZES = [(468, 60), (400, 50), (480, 60), (320, 40), (512, 64),
         (240, 30), (288, 36), (560, 70), (600, 75), (640, 80),
         (352, 44), (416, 52), (448, 56), (200, 25), (768, 96)]

KEYWORDS = ["anime", "manga", "sailor moon", "dragon ball", "sakura",
            "gundam", "kawaii", "neko", "chibi", "japan", "japanese",
            "otaku", "tenchi", "ranma", "slayers", "evangelion",
            "card captor", "magic knight", "pokemon", "digimon",
            "final fantasy", "ghibli", "seiyuu", "mecha", "shoujo"]

PAGE = 200
MAX_PAGES = 2


def get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search(kw: str, w: int, h: int, offset: int = 0):
    q = urllib.parse.quote(kw)
    u = (f"https://gifcities.org/special-search?q={q}&flavor=hybrid"
         f"&width={w}&height={h}&offset={offset}&page_size={PAGE}")
    html = get(u).decode("utf-8", "replace")
    return re.findall(
        r'<img width="(\d+)" height="(\d+)" '
        r'src="(https://blob\.gifcities\.org/gifcities/[^"]+\.gif)"', html)


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    index: dict[str, dict] = {}
    if INDEX.exists():
        index = json.loads(INDEX.read_text(encoding="utf-8"))

    only = sys.argv[1:]
    kws = only or KEYWORDS
    new = 0
    for w, h in SIZES:
        for kw in kws:
            for page in range(MAX_PAGES):
                try:
                    hits = search(kw, w, h, page * PAGE)
                except Exception as e:
                    print(f"[{w}x{h} {kw}] 搜索失败 {type(e).__name__}: {str(e)[:70]}")
                    break
                if not hits:
                    break
                for sw, sh, url in hits:
                    gid = url.rsplit("/", 1)[-1][:-4]
                    if gid in index and (DEST / f"{gid}.gif").exists():
                        continue
                    try:
                        data = get(url, timeout=20)
                    except Exception:
                        continue
                    if len(data) < 200:
                        continue
                    (DEST / f"{gid}.gif").write_bytes(data)
                    index[gid] = {"url": url, "w": w, "h": h, "kw": kw,
                                  "bytes": len(data)}
                    new += 1
                    time.sleep(0.05)
                print(f"[{w}x{h} {kw} p{page}] 命中 {len(hits)}，累计 {len(index)}")
                if len(hits) < PAGE:
                    break
            INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    print(f"\n完成：新增 {new}，索引 {len(index)} -> {INDEX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
