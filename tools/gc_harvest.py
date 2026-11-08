#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 GifCities 采集二次元候选 GIF，落盘并建索引。

GifCities = Internet Archive 对 GeoCities 的 GIF 归档，搜索页
``https://gifcities.org/search?q=<kw>`` 里每个 ``<div class="result">``
含一张 ``https://blob.gifcities.org/gifcities/<ID>.gif`` 直链。

用法::

    python tools/gc_harvest.py                 # 采集全部关键词
    python tools/gc_harvest.py sailor moon     # 只采指定关键词
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
DEST = ROOT / "gifs" / "gc"
INDEX = ROOT / "gifs" / "gc_index.json"

# 二次元向关键词；每词最多取 per_kw 张
KEYWORDS = [
    "sailor moon", "anime girl", "chibi anime", "dragon ball",
    "sakura", "anime dance", "kawaii anime", "anime eyes",
    "gundam", "neon genesis evangelion", "card captor sakura",
    "anime angel", "manga girl", "anime cat girl", "anime run",
    "anime flying", "anime sword", "anime magic", "anime star",
    "pokemon", "digimon", "ranma", "tenchi muyo",
]
PER_KW = 60


def get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def search(kw: str) -> list[tuple[str, int, int]]:
    """返回 [(blob_url, w, h)]。"""
    q = urllib.parse.quote(kw)
    html = get(f"https://gifcities.org/search?q={q}").decode("utf-8", "replace")
    out = []
    for m in re.finditer(
            r'<img width="(\d+)" height="(\d+)" src="(https://blob\.gifcities\.org/gifcities/[^"]+\.gif)"',
            html):
        out.append((m.group(3), int(m.group(1)), int(m.group(2))))
    return out


def main() -> int:
    kws = sys.argv[1:] or KEYWORDS
    if len(kws) == 1 and " " in kws[0]:
        kws = [kws[0]]
    DEST.mkdir(parents=True, exist_ok=True)

    index: dict[str, dict] = {}
    if INDEX.exists():
        index = json.loads(INDEX.read_text(encoding="utf-8"))

    total_new = 0
    for kw in kws:
        try:
            hits = search(kw)
        except Exception as e:
            print(f"[{kw}] 搜索失败 {type(e).__name__}: {str(e)[:80]}")
            continue
        # 先按源尺寸粗筛：太小的没细节，太大的多半是整页背景图
        hits = [h for h in hits if 24 <= h[1] <= 260 and 24 <= h[2] <= 260]
        print(f"[{kw}] 候选 {len(hits)} 张（已按源尺寸粗筛）")

        got = 0
        for url, w, h in hits:
            if got >= PER_KW:
                break
            gid = url.rsplit("/", 1)[-1][:-4]
            path = DEST / f"{gid}.gif"
            if gid in index and path.exists():
                continue
            try:
                data = get(url, timeout=20)
            except Exception as e:
                print(f"   ! 下载失败 {gid} {type(e).__name__}")
                continue
            if len(data) < 200:
                continue
            path.write_bytes(data)
            index[gid] = {"url": url, "src_w": w, "src_h": h, "kw": kw,
                          "bytes": len(data)}
            got += 1
            total_new += 1
            time.sleep(0.05)
        print(f"[{kw}] 新增 {got} 张，累计 {len(index)}")
        INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    print(f"\n完成：本次新增 {total_new}，索引共 {len(index)} 张 -> {INDEX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
