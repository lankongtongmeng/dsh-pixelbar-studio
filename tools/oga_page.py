#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓 OpenGameArt 条目页，列出可下载文件直链（opengameart.org/sites/default/files/...）。"""
from __future__ import annotations

import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "PixelBar-Research/1.0"}


def get(u: str) -> str:
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


for slug in sys.argv[1:]:
    u = slug if slug.startswith("http") else f"https://opengameart.org/content/{slug}"
    try:
        h = get(u)
    except Exception as e:
        print(f"FAIL {u}: {type(e).__name__} {e}")
        continue
    title = re.search(r"<title>(.*?)</title>", h, re.S)
    print("=" * 70)
    print("PAGE", u)
    print("TITLE", (title.group(1).strip() if title else "?")[:100])
    # 授权
    for m in re.finditer(r'(CC0|CC-BY-SA 3\.0|CC-BY-SA 4\.0|CC-BY 3\.0|CC-BY 4\.0|GPL \d|OGA-BY)', h):
        print("  LICENSE:", m.group(1))
        break
    # 文件直链
    files = sorted(set(re.findall(
        r'https://opengameart\.org/sites/default/files/[^"\'<>\s]+', h)))
    for f in files:
        print("  FILE:", urllib.parse.unquote(f))
    if not files:
        print("  （没有 sites/default/files 直链，可能是外链附件）")
        for m in sorted(set(re.findall(r'https?://[^"\'<>\s]+\.(?:zip|png|gif|tar\.gz)', h)))[:10]:
            print("  EXT :", m)


import urllib.parse  # noqa: E402
