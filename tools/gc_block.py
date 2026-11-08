#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印 GifCities 一条完整 result 块，找可用的元数据字段。"""
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(u):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


h = get("https://gifcities.org/search?q=sailor+moon")
blocks = re.findall(r'<div class="result">(.*?)</div>\s*(?=<div class="result">|</div>\s*</div>)',
                    h, re.S)
print("blocks:", len(blocks))
if blocks:
    print("=" * 70)
    print(blocks[0][:1800])
    print("=" * 70)
    print(blocks[1][:1200] if len(blocks) > 1 else "")

# 找 detail 链接与注释里的原始信息
for m in re.finditer(r'<!--(.*?)-->', h, re.S):
    t = m.group(1).strip()
    if t:
        print("COMMENT:", t[:400])
        break
