#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探 OpenGameArt 搜索页，列出条目与直链规律。"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(u):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


for q in ("anime", "pixel+art+character", "chibi"):
    u = f"https://opengameart.org/art-search-advanced?keys={q}&sort_by=count&sort_order=DESC"
    try:
        h = get(u)
    except Exception as e:
        print("FAIL", q, type(e).__name__, str(e)[:100])
        continue
    print("=" * 70)
    print("QUERY", q, "len", len(h))
    items = re.findall(r'<a href="(/content/[^"]+)"[^>]*>\s*([^<]{2,90}?)\s*</a>', h)
    seen = set()
    n = 0
    for path, title in items:
        if path in seen:
            continue
        seen.add(path)
        t = title.strip()
        if not t:
            continue
        print(f"  {t[:60]:62s} {path}")
        n += 1
        if n >= 12:
            break
