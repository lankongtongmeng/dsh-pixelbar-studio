#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 rank.json 的下标打印候选信息，并把选中项导出成清单。

用法::

    python tools/pick.py 9 13 15 ...            # 打印这些下标
    python tools/pick.py --rank gifs/wide_rank.json 0 1 2
"""
from __future__ import annotations

import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("idx", nargs="+", type=int)
    ap.add_argument("--rank", default=str(ROOT / "gifs" / "rank.json"))
    a = ap.parse_args()

    rows = json.loads(pathlib.Path(a.rank).read_text(encoding="utf-8"))
    for i in a.idx:
        if not (0 <= i < len(rows)):
            print(f"#{i} 越界（共 {len(rows)}）")
            continue
        r = rows[i]
        print(f'#{i:3d} score={r["score"]:5.2f} src={r["src"]:>9} '
              f'scaled={str(r["scaled"]):>9} frames={r["frames_used"]:2d} '
              f'alpha={int(r["alpha"])} ink={r["ink"]:.2f} mot={r["motion"]:.2f} '
              f'-> {r["path"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
