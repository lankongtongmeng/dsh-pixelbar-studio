#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对采集到的 GIF 批量评分，挑出适合 256x32 单色屏的素材。

评分维度（都是"能不能看"而不是"好不好看"的代理指标）：

* ``alpha``   有透明通道 → 抠图干净，强加分
* ``ink``     前景占比，太接近 0（看不见）或 1（实心方块）都扣分
* ``survive`` 前景缩到 28px 高再放回原尺寸后与原始掩码的 IoU —— **最关键**，
              直接衡量"缩到 32 像素高之后还认不认得出形状"
* ``motion``  相邻帧前景的变化比例，太低=静止、太高=闪烁
* ``edge``    周长/面积比，过高=细节噪声，缩完是糊的

用法::

    python tools/gif_rank.py                # 评分全部并打印 Top 40
    python tools/gif_rank.py --sheets 40    # 额外给 Top 40 生成预览拼图
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from pixelbar import render as rn  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "gifs" / "gc"
SHEETS = ROOT / "gifs" / "sheets"
OUT_JSON = ROOT / "gifs" / "rank.json"
MAX_FRAMES = 20


def iou(a, b) -> float:
    pa, pb = a.load(), b.load()
    inter = union = 0
    for y in range(a.height):
        for x in range(a.width):
            va, vb = bool(pa[x, y]), bool(pb[x, y])
            if va or vb:
                union += 1
                if va and vb:
                    inter += 1
    return inter / union if union else 0.0


def perimeter(mask) -> int:
    """前景像素中与背景 4-邻接的个数，近似周长。"""
    p = mask.load()
    n = 0
    for y in range(mask.height):
        for x in range(mask.width):
            if not p[x, y]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                xx, yy = x + dx, y + dy
                if not (0 <= xx < mask.width and 0 <= yy < mask.height) or not p[xx, yy]:
                    n += 1
                    break
    return n


def components(mask, min_px: int = 4) -> int:
    """连通域个数。

    **区分"画"和"文字/网页按钮"的关键指标**：文字是一行行小碎块 → 连通域极多，
    而角色/场景通常只有 1-3 个大块。只看墨量、存活率会被"About Us""Take Me Away"
    这类文字横幅骗到榜首。
    """
    w, h = mask.size
    p = mask.load()
    seen = [[False] * w for _ in range(h)]
    n = 0
    for sy in range(h):
        for sx in range(w):
            if seen[sy][sx] or not p[sx, sy]:
                continue
            stack = [(sx, sy)]
            seen[sy][sx] = True
            cnt = 0
            while stack:
                x, y = stack.pop()
                cnt += 1
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        xx, yy = x + dx, y + dy
                        if 0 <= xx < w and 0 <= yy < h and not seen[yy][xx] \
                                and p[xx, yy]:
                            seen[yy][xx] = True
                            stack.append((xx, yy))
            if cnt >= min_px:
                n += 1
    return n


def analyze(path: pathlib.Path, target_h: int = 28) -> dict | None:
    frames = rn.load_gif_rgba(path, max_frames=MAX_FRAMES, spread=True)
    if not frames:
        return None
    with Image.open(path) as im:
        total_frames = getattr(im, "n_frames", 1)
        src_size = im.size
    has_a = rn.has_transparency(frames[0])
    bgc = None if has_a else rn.auto_background(frames[0])
    masks = rn.gif_masks(frames, bg=("auto" if not has_a else None))
    bb = rn.union_bbox(masks)
    if bb is None:
        return {"path": str(path), "ok": False, "why": "无前景"}

    ux0, uy0, ux1, uy1 = bb
    cw, ch = ux1 - ux0, uy1 - uy0
    crops = [m.crop(bb) for m in masks]

    # 前景占比：并集掩码里有多少像素亮
    union = Image.new("1", (cw, ch), 0)
    up = union.load()
    for m in crops:
        mp = m.load()
        for y in range(ch):
            for x in range(cw):
                if mp[x, y]:
                    up[x, y] = 1
    # 注意：mode "1" 的 histogram() 把白色记在索引 **1**（不是 255），
    # 必须先 convert("L") 才是常规的 0/255 两桶。
    on_px = union.convert("L").histogram()[255]
    ink = on_px / (cw * ch)

    # 缩放存活率
    scale = target_h / ch
    tw = max(1, int(cw * scale))
    small = union.convert("L").resize((tw, target_h), Image.NEAREST)
    small = small.point(lambda v: 255 if v >= 128 else 0)
    back = small.resize((cw, ch), Image.NEAREST).point(lambda v: 255 if v >= 128 else 0)
    survive = iou(union.convert("L").point(lambda v: 255 if v else 0).convert("1"),
                  back.convert("1"))

    # 运动量：相邻帧（对齐后）前景差异
    diffs = []
    for i in range(1, len(crops)):
        a, b = crops[i - 1].load(), crops[i].load()
        d = sum(1 for y in range(ch) for x in range(cw) if bool(a[x, y]) != bool(b[x, y]))
        diffs.append(d / (cw * ch))
    motion = sum(diffs) / len(diffs) if diffs else 0.0

    edge = perimeter(union) / max(1, union.convert("L").histogram()[255])
    cc = components(union)

    try:
        rel = str(path.resolve().relative_to(ROOT))
    except ValueError:
        rel = str(path)
    return {
        "path": rel,
        "ok": True,
        "src": f"{src_size[0]}x{src_size[1]}",
        "frames_total": total_frames,
        "frames_used": len(frames),
        "alpha": has_a,
        "bg": bgc,
        "bbox": [cw, ch],
        "scaled": [tw, target_h],
        "ink": round(ink, 3),
        "survive": round(survive, 3),
        "motion": round(motion, 3),
        "edge": round(edge, 2),
        "cc": cc,
    }


def score(r: dict) -> float:
    """把指标压成一个排序分（只用于排序，不做判决）。"""
    s = 0.0
    s += 2.5 * r["survive"]                       # 形状能不能活下来，权重最高
    if r["alpha"]:
        s += 1.0
    if r["bg"] is not None:
        s += 0.4
    ink = r["ink"]
    if 0.10 <= ink <= 0.55:
        s += 1.2
    elif 0.05 <= ink <= 0.70:
        s += 0.5
    else:
        s -= 1.5
    m = r["motion"]
    if 0.02 <= m <= 0.45:
        s += 1.0
    elif m < 0.005:
        s -= 1.0
    e = r["edge"]
    if e <= 3.0:
        s += 0.8
    elif e >= 6.0:
        s -= 1.0
    tw = r["scaled"][0]
    if tw < 10:
        s -= 1.2                                  # 缩完太窄，看不出东西
    elif 24 <= tw <= 220:
        s += 0.6
    # 连通域越多越像文字/网页按钮，而不是"一幅画"
    cc = r.get("cc", 1)
    if cc <= 3:
        s += 1.5
    elif cc <= 8:
        s += 0.3
    elif cc >= 20:
        s -= 2.5
    else:
        s -= 0.8
    return round(s, 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheets", type=int, default=0, help="给 Top N 生成预览拼图")
    ap.add_argument("--limit", type=int, default=0, help="只评前 N 个（调试用）")
    ap.add_argument("--src", default=str(SRC), help="GIF 目录")
    ap.add_argument("--out", default=str(OUT_JSON), help="结果 JSON 路径")
    a = ap.parse_args()
    src = pathlib.Path(a.src).resolve()
    out_json = pathlib.Path(a.out).resolve()

    files = sorted(src.glob("*.gif"))
    if a.limit:
        files = files[:a.limit]
    print(f"评分 {len(files)} 个 GIF ...")

    rows, bad = [], 0
    for i, p in enumerate(files, 1):
        try:
            r = analyze(p)
        except Exception:
            bad += 1
            continue
        if not r or not r.get("ok"):
            bad += 1
            continue
        r["score"] = score(r)
        rows.append(r)
        if i % 100 == 0:
            print(f"  ... {i}/{len(files)}")

    rows.sort(key=lambda r: -r["score"])
    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"\n可用 {len(rows)}，解析失败 {bad}，结果 -> {out_json}\n")
    print(f"{'分':>5} {'存活':>5} {'墨':>5} {'动':>5} {'边':>5} {'帧':>4} "
          f"{'源':>9} {'缩后':>8} {'A':>2} 路径")
    for r in rows[:60]:
        print(f"{r['score']:5.2f} {r['survive']:5.2f} {r['ink']:5.2f} "
              f"{r['motion']:5.2f} {r['edge']:5.2f} {r['frames_used']:4d} "
              f"{r['src']:>9} {str(r['scaled']):>8} "
              f"{'Y' if r['alpha'] else '-':>2} {r['path']}")

    if a.sheets:
        SHEETS.mkdir(parents=True, exist_ok=True)
        for k, r in enumerate(rows[:a.sheets], 1):
            p = ROOT / r["path"]
            try:
                frames = rn.load_gif_rgba(p, max_frames=8, spread=True)
                masks = rn.gif_masks(frames, bg=None if r["alpha"] else "auto")
                tiles = [rn.mask_to_canvas(m, "height") for m in masks]
                sheet = rn.contact_sheet(tiles, cols=2, scale=1)
                sheet.save(SHEETS / f"{k:03d}_{p.stem}.png")
            except Exception:
                traceback.print_exc()
        print(f"\n预览拼图 -> {SHEETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
