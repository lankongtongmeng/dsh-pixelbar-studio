#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓 OpenGameArt 条目页的「授权 / 署名要求」原文，用于写进文档。"""
from __future__ import annotations

import html
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 PixelBar-Research/1.0"}

for slug in sys.argv[1:]:
    u = slug if slug.startswith("http") else f"https://opengameart.org/content/{slug}"
    req = urllib.request.Request(u, headers=UA)
    h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    print("=" * 72)
    print(u)
    # 授权名
    for m in re.finditer(r"<div class='license-name'>([^<]+)</div>", h):
        print("  LICENSE:", m.group(1))
    # 署名要求
    m = re.search(r"field-name-field-copyright-notice(.*?)field-name-field",
                  h, re.S)
    if m:
        t = re.sub(r"<[^>]+>", " ", m.group(1))
        print("  ATTRIBUTION:", re.sub(r"\s+", " ", html.unescape(t)).strip()[:600])
    # 正文里的作者/来源
    m = re.search(r'field-name-body(.*?)field-name-field', h, re.S)
    if m:
        t = re.sub(r"<[^>]+>", " ", m.group(1))
        t = re.sub(r"\s+", " ", html.unescape(t)).strip()
        print("  BODY:", t[:600])
