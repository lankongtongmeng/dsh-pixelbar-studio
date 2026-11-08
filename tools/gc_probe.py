#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探 GifCities 结果页结构，找出 gif 直链规律。"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(u):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


h = get("https://gifcities.org/search?q=anime")
print("len", len(h))

# 找 img 标签
imgs = re.findall(r'<img[^>]+>', h)
print("img tags:", len(imgs))
for t in imgs[:8]:
    print("  ", t[:220])

# 找所有 http 链接
urls = set(re.findall(r'https?://[^\s"\'<>]+', h))
gifs = sorted(u for u in urls if ".gif" in u.lower())
print("gif urls:", len(gifs))
for u in gifs[:12]:
    print("  ", u)

# 找结果容器 class
for m in re.finditer(r'class="([^"]+)"', h):
    pass
classes = sorted(set(re.findall(r'class="([^"]+)"', h)))
print("classes:", classes[:30])

# 分页/总数线索
for kw in ("results", "result", "found", "page=", "total"):
    for m in re.finditer(kw, h, re.I):
        s = max(0, m.start() - 80)
        print(f"  [{kw}] ...{h[s:m.start()+90]}...".replace("\n", " "))
        break
