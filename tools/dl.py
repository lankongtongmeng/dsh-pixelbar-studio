#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用素材下载器（Python urllib，绕开 PowerShell 的 TLS 问题）。

用法::

    python tools/dl.py <url> [<url> ...] --out gifs/oga
"""
from __future__ import annotations

import argparse
import pathlib
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "PixelBar-Research/1.0"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--out", default="gifs/dl")
    ap.add_argument("--name", nargs="*", default=[], help="对应每个 url 的保存名")
    a = ap.parse_args()

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for i, u in enumerate(a.urls):
        name = a.name[i] if i < len(a.name) else urllib.parse.unquote(
            u.rsplit("/", 1)[-1])
        name = name.replace(" ", "_")
        try:
            req = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            (out / name).write_bytes(data)
            print(f"OK  {len(data):>9,} B  {name}")
        except Exception as e:
            print(f"FAIL {type(e).__name__}: {str(e)[:90]}  {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
