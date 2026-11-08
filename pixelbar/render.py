#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""绘制层：把文字 / 图片 / GIF 变成 256x32 单色画布。

要点（均为实机踩坑结论）：

* 屏只有 32 像素高 → **中文最小可读字号 12px、舒适 16px**，故中文每屏最多 2 行；
  四行只能用 ASCII 5x7 点阵（scale=1 字高 7 可 4 行，scale=2 字高 14 可 2 行）。
* 中文必须用宋体（simsun.ttc）+ FreeType ``getmask(mode="L")`` 阈值二值化；
  微软雅黑 8px 抗锯齿会糊成一团。**不要用** ``getmask(mode="1")``：
  其字节布局与 ``Image.frombytes`` 不兼容，会渲染成横条垃圾。
* 屏是 8:1 超宽条，方形素材天生吃亏；横向运动的内容最合适。
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

from .font5x7 import FONT_5X7

WIDTH, HEIGHT = 256, 32
CJK_FONT = r"C:\Windows\Fonts\simsun.ttc"
MONO_FONT = r"C:\Windows\Fonts\consola.ttf"

# Bayer 8x8 有序抖动矩阵（灰度 → 单色时保留层次）
BAYER8 = [
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
]


# ---------------------------------------------------------------- 画布

def new_canvas():
    """32 行 x 256 列，非 0 即亮。"""
    return [[0] * WIDTH for _ in range(HEIGHT)]


def canvas_to_image(canvas, scale: int = 1):
    """画布 -> PIL 灰度图（预览用）。"""
    img = Image.new("L", (WIDTH, HEIGHT), 0)
    p = img.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if canvas[y][x]:
                p[x, y] = 255
    if scale > 1:
        img = img.resize((WIDTH * scale, HEIGHT * scale), Image.NEAREST)
    return img


def canvas_from_image(img, mode: str = "threshold", thr: int = 128,
                      fit: str = "stretch"):
    """PIL 图 -> 画布。

    mode: ``threshold``（阈值）/ ``dither``（Bayer 抖动，保留灰度层次）
    fit : ``stretch`` 拉伸铺满 / ``height`` 保高居中 / ``width`` 保宽裁切
    """
    g = _fit(img.convert("L"), fit)
    p = g.load()
    canvas = new_canvas()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            v = p[x, y]
            if mode == "dither":
                canvas[y][x] = 1 if v > BAYER8[y % 8][x % 8] * 4 else 0
            else:
                canvas[y][x] = 1 if v >= thr else 0
    return canvas


def _fit(img, fit: str):
    if fit == "stretch":
        return img.resize((WIDTH, HEIGHT), Image.LANCZOS)
    if fit == "height":
        r = HEIGHT / img.height
        nw = max(1, int(img.width * r))
        g = img.resize((nw, HEIGHT), Image.LANCZOS)
        out = Image.new("L", (WIDTH, HEIGHT), 0)
        out.paste(g, (max(0, (WIDTH - nw) // 2), 0))
        return out
    if fit == "width":
        r = WIDTH / img.width
        nh = max(1, int(img.height * r))
        g = img.resize((WIDTH, nh), Image.LANCZOS)
        top = max(0, (nh - HEIGHT) // 2)
        g = g.crop((0, top, WIDTH, min(nh, top + HEIGHT)))
        out = Image.new("L", (WIDTH, HEIGHT), 0)
        out.paste(g, (0, (HEIGHT - g.height) // 2))
        return out
    raise ValueError(f"未知 fit: {fit}")


def blit(canvas, img, x, y, invert: bool = False):
    """把 1 位图贴到画布，越界自动裁掉。"""
    p = img.convert("1").load()
    for yy in range(img.height):
        ty = y + yy
        if not (0 <= ty < HEIGHT):
            continue
        for xx in range(img.width):
            tx = x + xx
            if 0 <= tx < WIDTH:
                on = bool(p[xx, yy])
                if invert:
                    on = not on
                if on:
                    canvas[ty][tx] = 1
    return canvas


# ---------------------------------------------------------------- ASCII 点阵

def draw_char(canvas, x: int, y: int, char: str, scale: int = 1) -> int:
    """画一个字符，返回步进宽度。"""
    glyph = FONT_5X7.get(char.upper(), FONT_5X7.get(" ", ["00000"] * 7))
    for r, rowbits in enumerate(glyph):
        for c, bit in enumerate(rowbits):
            if bit != "1":
                continue
            for dy in range(scale):
                for dx in range(scale):
                    px, py = x + c * scale + dx, y + r * scale + dy
                    if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        canvas[py][px] = 1
    return 6 * scale


def draw_ascii(canvas, x: int, y: int, text: str, scale: int = 1) -> int:
    for ch in text:
        x += draw_char(canvas, x, y, ch, scale)
        if x >= WIDTH:
            break
    return x


def draw_ascii_lines(canvas, lines, scale: int = 2, y0: int | None = None):
    """逐行水平居中。scale=1 字高 7（最多 4 行）；scale=2 字高 14（最多 2 行）。"""
    glyph_h = 7 * scale
    step = 8 * scale
    gap = step - glyph_h
    if y0 is None:
        total = step * len(lines) - gap
        y0 = max(1, (HEIGHT - total) // 2)
    for i, line in enumerate(lines):
        if not line:
            continue
        text = line.upper()
        width = len(text) * 6 * scale - scale
        draw_ascii(canvas, max(0, (WIDTH - width) // 2), y0 + i * step, text, scale)
    return canvas


# ---------------------------------------------------------------- 中文

def render_mask(text: str, size: int = 16, thr: int = 128,
                font_path: str = CJK_FONT):
    """FreeType 灰度掩码 -> 阈值二值化（**不要**用 getmask(mode='1')）。"""
    font = ImageFont.truetype(font_path, size)
    mask = font.getmask(text, mode="L")
    img = Image.frombytes("L", mask.size, bytes(mask))
    return img.point(lambda v: 255 if v >= thr else 0).convert("1")


def draw_cjk(canvas, x: int, y: int, text: str, size: int = 16, thr: int = 128):
    return blit(canvas, render_mask(text, size, thr), x, y)


def draw_cjk_lines(canvas, lines, size: int = 16, thr: int = 128,
                   line_gap: int = 0, y0: int | None = None):
    """中文按 size 像素一行。32px 高 → 16px 最多 2 行。"""
    step = size + line_gap
    if y0 is None:
        total = step * len(lines) - line_gap
        y0 = max(0, (HEIGHT - total) // 2)
    for i, line in enumerate(lines):
        if not line:
            continue
        img = render_mask(line, size, thr)
        blit(canvas, img, max(0, (WIDTH - img.width) // 2), y0 + i * step)
    return canvas


def draw_mixed(canvas, cjk_line: str, ascii_lines, cjk_size: int = 16):
    """首行中文（16px，占 y0-15）+ 其余 ASCII 点阵（7px，占 y16 起）。"""
    draw_cjk_lines(canvas, [cjk_line], size=cjk_size, y0=0)
    draw_ascii_lines(canvas, ascii_lines[:2], scale=1, y0=17)
    return canvas


# ---------------------------------------------------------------- 图形

def draw_rect(canvas, x: int, y: int, w: int, h: int, fill: bool = False):
    for xx in range(x, x + w):
        for yy in (y, y + h - 1):
            if 0 <= xx < WIDTH and 0 <= yy < HEIGHT:
                canvas[yy][xx] = 1
    for yy in range(y, y + h):
        for xx in (x, x + w - 1):
            if 0 <= xx < WIDTH and 0 <= yy < HEIGHT:
                canvas[yy][xx] = 1
    if fill:
        for yy in range(y + 1, y + h - 1):
            for xx in range(x + 1, x + w - 1):
                if 0 <= xx < WIDTH and 0 <= yy < HEIGHT:
                    canvas[yy][xx] = 1
    return canvas


def draw_bar(canvas, x: int, y: int, w: int, h: int, pct: float):
    """进度条。"""
    pct = max(0.0, min(100.0, pct))
    fill = int((w - 2) * pct / 100)
    draw_rect(canvas, x, y, w, h)
    for yy in range(y + 1, y + h - 1):
        for xx in range(x + 1, x + 1 + fill):
            if 0 <= xx < WIDTH and 0 <= yy < HEIGHT:
                canvas[yy][xx] = 1
    return canvas


def border(canvas, ticks_every: int = 32, crosshair: bool = True):
    """1px 满边框 + 顶部刻度 + 中心十字：对齐自检用（任何平移都会露馅）。"""
    for x in range(WIDTH):
        canvas[0][x] = 1
        canvas[HEIGHT - 1][x] = 1
    for y in range(HEIGHT):
        canvas[y][0] = 1
        canvas[y][WIDTH - 1] = 1
    if ticks_every:
        for x in range(0, WIDTH, ticks_every):
            for y in range(1, 4):
                canvas[y][x] = 1
    if crosshair:
        for x in range(WIDTH // 2 - 8, WIDTH // 2 + 9):
            canvas[HEIGHT // 2][x] = 1
        for y in range(HEIGHT // 2 - 3, HEIGHT // 2 + 4):
            canvas[y][WIDTH // 2] = 1
    return canvas


# ---------------------------------------------------------------- 动图 / 素材
#
# 网页 GIF（尤其 GeoCities 那批二次元素材）有三个坑，旧的"亮度阈值 + 取前 N 帧"
# 处理法全踩：
#   1. **透明背景 GIF 的透明像素在 RGB 里常是黑/白** → 亮度阈值会把整块背景当
#      前景，出来是一整片实心方块。必须先看 alpha 通道。
#   2. 不透明但**纯色背景**（白底/洋红底）的素材同样被整块吃掉 → 需采样边框推底色。
#   3. 只取前 N 帧会把循环动画截断成"只播前三分之一" → 必须均匀抽样覆盖整个循环。

def _lum(r: int, g: int, b: int) -> int:
    return (r * 299 + g * 587 + b * 114) // 1000


def has_transparency(frame, alpha_min: int = 128, frac: float = 0.02) -> bool:
    """帧里真正被抠掉的像素是否够多（有些 GIF 挂着透明索引但其实全不透明）。"""
    a = frame.getchannel("A")
    hist = a.histogram()
    return sum(hist[:alpha_min]) >= frame.width * frame.height * frac


def auto_background(frame, min_frac: float = 0.55):
    """从四条边框采样推断统一底色；无统一底色返回 None。

    颜色按每通道 5 位量化后再取众数，避免 GIF 抖动噪声打散统计。
    """
    w, h = frame.size
    px = frame.load()
    counts: dict[tuple[int, int, int], int] = {}
    for x in range(w):
        for y in (0, h - 1):
            r, g, b = px[x, y][:3]
            k = (r >> 3, g >> 3, b >> 3)
            counts[k] = counts.get(k, 0) + 1
    for y in range(h):
        for x in (0, w - 1):
            r, g, b = px[x, y][:3]
            k = (r >> 3, g >> 3, b >> 3)
            counts[k] = counts.get(k, 0) + 1
    if not counts:
        return None
    k, n = max(counts.items(), key=lambda kv: kv[1])
    if n < (2 * w + 2 * h) * min_frac:
        return None
    return (k[0] << 3 | 4, k[1] << 3 | 4, k[2] << 3 | 4)


def frame_foreground(frame, thr: int = 128, invert: bool = False, bg="auto",
                     bg_tol: int = 96, alpha_min: int = 128, alpha=None):
    """RGBA 帧 -> ``1`` 位前景掩码。

    判定优先级：**alpha 通道 > 纯色底色剔除 > 亮度阈值**。

    * ``alpha=True/False`` 强制走 / 不走透明通道；``None`` 自动判断
    * ``bg=None`` 关掉底色剔除；``bg=(r,g,b)`` 手动指定底色
    * ``invert`` 只影响最后的亮度阈值分支（默认"暗=前景"）
    """
    w, h = frame.size
    px = frame.load()
    m = Image.new("1", (w, h), 0)
    mp = m.load()

    if alpha is None:
        alpha = has_transparency(frame, alpha_min)
    if alpha:
        for y in range(h):
            for x in range(w):
                if px[x, y][3] >= alpha_min:
                    mp[x, y] = 1
        return m

    bgc = auto_background(frame) if bg == "auto" else bg
    if bgc is not None:
        for y in range(h):
            for x in range(w):
                r, g, b = px[x, y][:3]
                if abs(r - bgc[0]) + abs(g - bgc[1]) + abs(b - bgc[2]) > bg_tol:
                    mp[x, y] = 1
        return m

    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            v = _lum(r, g, b)
            if (v >= thr) if invert else (v < thr):
                mp[x, y] = 1
    return m


def load_gif_rgba(path, max_frames: int = 20, trim_bottom: int = 0,
                  spread: bool = True):
    """读 GIF 为 RGBA 帧列表（保留透明通道）。

    ``spread=True`` 时**均匀抽样覆盖整个循环**，而不是只取前 N 帧 —— 后者会让
    长循环动画只剩开头一小段。PIL 在 seek 时会自动做帧合成与 dispose 处理。
    """
    frames = []
    with Image.open(path) as img:
        total = getattr(img, "n_frames", 1)
        if spread and total > max_frames:
            if max_frames <= 1:
                idxs = [0]
            else:
                idxs = sorted({round(i * (total - 1) / (max_frames - 1))
                               for i in range(max_frames)})
        else:
            idxs = list(range(min(total, max_frames)))
        for i in idxs:
            img.seek(i)
            g = img.convert("RGBA")
            if trim_bottom:
                g = g.crop((0, 0, g.width, max(1, g.height - trim_bottom)))
            frames.append(g.copy())
    return frames


def gif_masks(frames, thr: int = 128, invert: bool = False, bg="auto",
              bg_tol: int = 96, alpha_min: int = 128, alpha=None):
    """RGBA 帧列表 -> ``1`` 位掩码列表。"""
    return [frame_foreground(f, thr, invert, bg, bg_tol, alpha_min, alpha)
            for f in frames]


def union_bbox(masks):
    """所有帧的并集包围盒（共用可避免逐帧抖动）。全空返回 None。"""
    ux0, uy0, ux1, uy1 = 10 ** 9, 10 ** 9, -1, -1
    for m in masks:
        bb = m.getbbox()
        if not bb:
            continue
        ux0, uy0 = min(ux0, bb[0]), min(uy0, bb[1])
        ux1, uy1 = max(ux1, bb[2]), max(uy1, bb[3])
    return None if ux1 <= 0 else (ux0, uy0, ux1, uy1)


def mask_to_canvas(mask, fit: str = "height"):
    """``1`` 位掩码 -> 256x32 画布（按 fit 适配后阈值化）。"""
    g = _fit(mask.convert("L"), fit).point(lambda v: 255 if v >= 128 else 0)
    p = g.load()
    canvas = new_canvas()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if p[x, y]:
                canvas[y][x] = 1
    return canvas


def gif_frames(path, max_frames: int = 20, thr: int = 128, invert: bool = False,
               trim_bottom: int = 0, target_h: int = 28, travel: bool = True,
               ground: int | None = 28, gap: int = 0, mode: str = "sprite",
               bg="auto", bg_tol: int = 96, alpha=None, spread: bool = True,
               fit: str = "height"):
    """GIF -> 一组 256x32 画布。

    * ``mode="sprite"``（默认）：抠出前景，按 ``target_h`` 缩放，横穿或原地循环
    * ``mode="scene"``：整帧铺进 256x32（``fit`` 取 stretch/height/width），
      适合本身就是宽幅的动画或整屏滚动类素材
    * ``spread``：长循环均匀抽样而非截断前 N 帧
    * ``bg``：``"auto"`` 自动推底色 / ``None`` 关掉 / ``(r,g,b)`` 手动指定
    """
    frames = load_gif_rgba(path, max_frames, trim_bottom, spread)
    if not frames:
        raise ValueError(f"{path} 里没有帧")
    masks = gif_masks(frames, thr, invert, bg, bg_tol, alpha=alpha)

    if mode == "scene":
        return [mask_to_canvas(m, fit) for m in masks]

    bb = union_bbox(masks)
    if bb is None:
        raise ValueError("阈值后没有找到前景像素，试试调整 --thr / --invert / --bg")

    ux0, uy0, ux1, uy1 = bb
    cw, ch = ux1 - ux0, uy1 - uy0
    scale = target_h / ch
    tw, th = max(1, int(cw * scale)), target_h

    tiles = []
    for m in masks:
        c = m.crop((ux0, uy0, ux1, uy1)).convert("L")
        c = c.resize((tw, th), Image.NEAREST).point(lambda v: 255 if v >= 128 else 0)
        tiles.append(c)

    n = len(tiles)
    out = []
    span = WIDTH + tw + gap
    for i in range(n):
        canvas = new_canvas()
        if ground is not None:
            for x in range(WIDTH):
                canvas[ground][x] = 1
            off = (i * 12) % 24                      # 滚动虚线，提示速度
            for x in range(-24, WIDTH, 24):
                for k in range(8):
                    xx = x + off + k
                    if 0 <= xx < WIDTH and ground + 2 < HEIGHT:
                        canvas[ground + 2][xx] = 1
        hx = int(WIDTH - (i / n) * span) if travel else (WIDTH - tw) // 2
        hy = (ground - th) if ground is not None else (HEIGHT - th) // 2
        canvas = blit(canvas, tiles[i], hx, hy)
        out.append(canvas)
    return out


def contact_sheet(canvases, path=None, cols: int = 4, scale: int = 2):
    """把多帧拼成一张对比图，便于肉眼检查。"""
    rows = (len(canvases) + cols - 1) // cols
    sheet = Image.new("L", (WIDTH * cols + (cols - 1) * 4,
                            (HEIGHT + 4) * rows), 0)
    for i, c in enumerate(canvases):
        r, col = divmod(i, cols)
        sheet.paste(canvas_to_image(c), (col * (WIDTH + 4), r * (HEIGHT + 4)))
    if scale > 1:
        sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)
    if path:
        sheet.save(path)
    return sheet
