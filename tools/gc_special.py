#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探 GifCities special-search：能不能按尺寸/宽高比检索（找 468x60 横幅类）。"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(u):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


h = get("https://gifcities.org/special-search")
print("len", len(h))
# 打印表单结构
for m in re.finditer(r'<form.*?</form>', h, re.S):
    print("=" * 60)
    print(m.group(0)[:2500])
print("=" * 60)
for m in re.finditer(r'<(input|select|option)[^>]*>', h):
    print("  ", m.group(0)[:200])
