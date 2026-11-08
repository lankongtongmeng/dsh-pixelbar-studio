#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精灵表切片 + 行走场景合成。

素材：Pepper&Carrot 24x32 角色表（CC0，David Revoy）。
表结构已实测定死：**左上角 3 列 x 4 行、每格 24x32**，右侧是人像大图。
每行一个朝向（背/侧/正/另一侧），每列一个行走帧。

合成思路（8:1 超宽条的关键）：**角色原地走、背景横向滚动**。
让角色横穿整屏在 20 帧内会快到像瞬移；原地循环 + 视差背景才有"一直在走"的
连续感，而且首尾天然接得上。
"""
from __future__ import annotations

import pathlib

from PIL import Image

from . import render as rn

CELL_W, CELL_H = 24, 32
COLS, ROWS = 3, 4


def flat_background(im, min_frac: float = 0.20, bits: int = 5):
    """整图主色（量化后取众数）——角色表底色常是**双色**（青绿底 + 灰色人像区），
    边框采样法会返回 None，必须按整图众数判底色。"""
    small = im.convert("RGB")
    counts: dict[tuple[int, int, int], int] = {}
    px = small.load()
    w, h = small.size
    step = max(1, int((w * h / 20000) ** 0.5))     # 大图抽样，够用且快
    total = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b = px[x, y]
            k = (r >> (8 - bits), g >> (8 - bits), b >> (8 - bits))
            counts[k] = counts.get(k, 0) + 1
            total += 1
    if not counts:
        return None
    k, n = max(counts.items(), key=lambda kv: kv[1])
    if n < total * min_frac:
        return None
    sh = 8 - bits
    return (k[0] << sh | (1 << (sh - 1)), k[1] << sh | (1 << (sh - 1)),
            k[2] << sh | (1 << (sh - 1)))


def slice_sheet(path, cell=(CELL_W, CELL_H), cols=COLS, rows=ROWS,
                bg_tol: int = 70, origin=(0, 0)):
    """角色表 -> ``rows[r][c]`` 的 24x32 前景掩码（``1`` 位 PIL 图）。

    底色必须在**要切的网格区域内**取众数：整表常是双色（青绿角色区 + 灰色人像区），
    按整图取众数会选中灰色区，青绿底色反而被当成前景，切出来整格全白。
    """
    cw, ch = cell
    ox, oy = origin
    im = Image.open(path).convert("RGBA")
    box = (ox, oy, ox + cols * cw, oy + rows * ch)
    region = im.crop(box)
    if rn.has_transparency(region):
        mask = region.getchannel("A").point(
            lambda v: 255 if v >= 96 else 0).convert("1")
    else:
        bgc = flat_background(region)
        mask = rn.frame_foreground(region, bg=bgc, bg_tol=bg_tol)
    out = []
    for r in range(rows):
        line = []
        for c in range(cols):
            line.append(mask.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)))
        out.append(line)
    return out


def content_bbox(frames):
    """一组掩码的并集内容包围盒（用于把脚对到地面线）。"""
    return rn.union_bbox(frames)


# ---------------------------------------------------------------- 背景元素

def _hill(x: int, period: int = 96, amp: int = 5, base: int = 25) -> int:
    """周期性的"远山"轮廓高度（用三角波，避免浮点与查表）。"""
    t = x % period
    half = period // 2
    d = t if t < half else period - t
    return base - int(d * amp / half)


def _skyline(x: int, period: int = 128, base: int = 24) -> int:
    """周期性"城市天际线"高度（阶梯状，pixel art 味道）。"""
    t = x % period
    steps = [3, 7, 2, 9, 4, 11, 5, 8, 2, 6, 10, 4, 7, 3, 9, 5]
    return base - steps[(t // (period // len(steps))) % len(steps)]


# 各背景风格的横向循环周期（像素）。bg_speed = 周期 / 帧数 时动画首尾无缝。
STYLE_PERIOD = {"ground": 24, "hills": 48, "skyline": 72, "stars": 24,
                "petals": 24}


def draw_background(canvas, offset: int, ground: int = 29, style: str = "hills"):
    """画视差背景。

    **只画轮廓（1px），不填充**：1 位屏上背景一旦填实，就会和同样是"实心"的角色
    糊成一片，角色直接消失。这是本屏最容易踩的观感坑。
    """
    if style == "hills":
        for x in range(rn.WIDTH):
            y = _hill(x + offset, period=48, amp=4, base=ground - 6)
            if 0 <= y < ground:
                canvas[y][x] = 1
        for x in range(rn.WIDTH):
            y = _hill(x + offset * 2 + 16, period=48, amp=3, base=ground - 2)
            if 0 <= y < ground:
                canvas[y][x] = 1
    elif style == "skyline":
        # 楼要宽、要有间隔；窄楼密排会变成一片锯齿噪声
        period = 72
        widths = [26, 20, 22]
        heights = [8, 14, 6]
        t = offset % period
        x = -t
        k = 0
        while x < rn.WIDTH:
            bw = widths[k % len(widths)]
            bh = heights[k % len(heights)]
            top = ground - 1 - bh
            for xx in range(max(0, x), min(rn.WIDTH, x + bw)):
                if 0 <= top < ground:
                    canvas[top][xx] = 1
            for xx in (x, x + bw - 1):
                if 0 <= xx < rn.WIDTH:
                    for y in range(max(0, top), ground):
                        canvas[y][xx] = 1
            x += bw + 4
            k += 1
    elif style == "stars":
        # 只放 10 颗，且只在上半部 —— 满屏星点会盖过角色
        for k in range(10):
            sx = (k * 97 - offset) % rn.WIDTH
            sy = 3 + (k * 5) % 9
            if 0 <= sy < ground - 8:
                canvas[sy][sx] = 1
    elif style == "petals":                            # 飘落的花瓣（稀疏单像素）
        for k in range(7):
            sx = (k * 61 + offset * 2) % rn.WIDTH
            sy = (k * 13 + offset) % max(1, ground - 3)
            if 0 <= sy < ground - 1:
                canvas[sy][sx] = 1
    # 地面线
    for x in range(rn.WIDTH):
        canvas[ground][x] = 1
    # 地面下的滚动虚线（提示速度）
    if ground + 1 < rn.HEIGHT:
        off = offset % 24
        for x in range(-24, rn.WIDTH, 24):
            for k in range(8):
                xx = x + off + k
                if 0 <= xx < rn.WIDTH:
                    canvas[ground + 1][xx] = 1


def walk_scene(actors, n_frames: int = 18, ground: int = 29,
               style: str = "ground", bg_speed: float | None = None):
    """多角色行走场景 -> 画布列表。

    ``actors`` 每项：``{"sheet": 路径或已切网格, "row": 1, "x": 80,
    "flip": False, "bob": True}``。

    **无缝循环的两个硬约束**（不做就会看到"卡一下"）：

    * ``n_frames`` 必须是行走帧数（3）的整数倍，否则最后一帧到第一帧的走姿倒退；
    * ``bg_speed * n_frames`` 必须是背景周期（``STYLE_PERIOD``）的整数倍，
      否则地面/背景跳变。

    默认 ``n_frames=18``，``bg_speed`` 自动取 ``周期 / n_frames``，两条同时满足。
    """
    if bg_speed is None:
        bg_speed = STYLE_PERIOD.get(style, 24) / n_frames

    prepared = []
    for act in actors:
        grid = act["sheet"] if isinstance(act["sheet"], list) \
            else slice_sheet(act["sheet"])
        row = act.get("row", 1)
        bb = content_bbox(grid[row])
        if bb is None:
            raise ValueError(f"第 {row} 行没有内容")
        tiles = [m.crop(bb) for m in grid[row]]
        if act.get("flip"):
            tiles = [t.transpose(Image.FLIP_LEFT_RIGHT) for t in tiles]
        tw, th = tiles[0].size
        x = act.get("x")
        if x is None:
            x = (rn.WIDTH - tw) // 2
        prepared.append({
            "tiles": tiles, "x": x, "y": ground - th,
            "bob": act.get("bob", True),
        })

    out = []
    for i in range(n_frames):
        canvas = rn.new_canvas()
        draw_background(canvas, int(i * bg_speed), ground, style)
        for a in prepared:
            tile = a["tiles"][i % len(a["tiles"])]
            dy = -1 if (a["bob"] and (i % len(a["tiles"])) == 1) else 0
            canvas = rn.blit(canvas, tile, a["x"], a["y"] + dy)
        out.append(canvas)
    return out


def walk_canvases(sheet, row: int = 1, n_frames: int = 18, ground: int = 29,
                  style: str = "ground", bg_speed: float | None = None,
                  x: int | None = None, bob: bool = True, flip: bool = False):
    """单角色行走场景（``walk_scene`` 的薄封装）。

    * ``sheet``    : 角色表路径，或已切好的 ``rows[r][c]`` 网格
    * ``row``      : 用第几行（朝向）；侧视一般是第 1/3 行，正面是第 0/2 行
    * ``n_frames`` : 输出帧数（默认 18，是 3 帧走姿的整数倍，循环无缝）
    * ``ground``   : 地面线所在行
    * ``style``    : ground（默认，只有地面线+虚线，最干净）/ hills / skyline /
                     stars / petals
    * ``bg_speed`` : 背景每帧滚动像素；默认 ``24/n_frames``（虚线周期整除）
    * ``x``        : 角色左边缘列；None = 水平居中
    """
    return walk_scene([{"sheet": sheet, "row": row, "x": x, "bob": bob,
                        "flip": flip}],
                      n_frames=n_frames, ground=ground, style=style,
                      bg_speed=bg_speed)
