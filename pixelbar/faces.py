#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""表情：把 6 张脸"烧"进各自的 category，运行时 2ms 级瞬时切换。

架构（借鉴 wafer-pixel 的思路，代码自研）：

    每个表情占**独立的一个 category**，表情图用 0x17 一次性烧进去；
    运行时切换只是发一条 0xEF 命令（约 2ms），**不需要重新上传**。
    category 内部换 slot 才需要重传（慢），所以运行时绝不这么做。

    category 2 = normal    3 = happy    4 = sad
             5 = angry     6 = thinking 7 = celebrate

⚠️ 会覆盖这些 category 原生的内置场景（办公/阅读/猫/狗/热词/赛博）。
   原生时钟(0)、游戏(1)、频谱(8) 不受影响。

脸部设计针对 8:1 超宽屏：**宽脸**，双眼拉开到中心两侧 ±36，
而不是把方脸缩在中间（那样只剩一小块）。
"""
from __future__ import annotations

from .render import HEIGHT, WIDTH, canvas_to_image, new_canvas

# --- 脸部几何（针对 256x32 优化，三段式垂直布局）---
EYE_DX = 36          # 双眼距中心
BROW_CY = 3          # 眉毛行
EYE_CY = 11          # 眼睛中心行（眼球占 y 7..15）
EYE_R = 4            # 眼球半径
MOUTH_TOP = 20       # 嘴巴上沿（笑曲线起点）；撇嘴则用 MOUTH_TOP+6 作两端

EXPRESSIONS = ["normal", "happy", "sad", "angry", "thinking", "celebrate"]

# 表情 -> category（一个表情一个 category）
EXPRESSION_CATEGORY = {
    "normal": 2, "happy": 3, "sad": 4,
    "angry": 5, "thinking": 6, "celebrate": 7,
}
CATEGORY_EXPRESSION = {v: k for k, v in EXPRESSION_CATEGORY.items()}

LABELS = {
    "normal": "平静", "happy": "开心", "sad": "难过",
    "angry": "生气", "thinking": "思考", "celebrate": "庆祝",
}


# ---------------------------------------------------------------- 绘制原语

def _px(c, x, y):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        c[y][x] = 1


def disc(c, cx, cy, r):
    """实心圆。"""
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                _px(c, cx + dx, cy + dy)
    return c


def ring(c, cx, cy, r, thick=1):
    """圆环。"""
    inner = (r - thick) ** 2
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d = dx * dx + dy * dy
            if inner < d <= r * r:
                _px(c, cx + dx, cy + dy)
    return c


def line(c, x0, y0, x1, y1):
    """Bresenham 直线。"""
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        _px(c, x0, y0)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return c


def curve(c, cx, cy, w, h, down=True, thick=1):
    """抛物线。down=True 开口向下（U 形 = 笑）；False 开口向上（∩ 形 = 撇嘴）。"""
    half = max(1, w // 2)
    for x in range(cx - half, cx + half + 1):
        t = (x - cx) / half
        off = int(round(h * (1 - t * t)))
        y = cy + off if down else cy - off
        for k in range(thick):
            _px(c, x, y + k)
    return c


def sparkle(c, cx, cy, size=5):
    """四角星（庆祝用）。size 为臂长。"""
    line(c, cx - size, cy, cx + size, cy)
    line(c, cx, cy - size, cx, cy + size)
    for d in range(1, size // 2 + 1):
        _px(c, cx + d, cy + d)
        _px(c, cx - d, cy + d)
        _px(c, cx + d, cy - d)
        _px(c, cx - d, cy - d)
    return c


def brow(c, cx, cy, tilt, w=13, thick=2):
    """眉毛。tilt>0 = 内低外高（生气）；tilt<0 = 内高外低（难过）。

    画在眼睛上方独立的行上（BROW_CY），不要贴着 EYE_CY，否则会与眼球相撞。
    """
    for k in range(thick):
        line(c, cx - w, cy + tilt + k, cx + w, cy - tilt + k)
    return c


# ---------------------------------------------------------------- 表情

def draw_face(name: str):
    """生成某个表情的画布。"""
    if name not in EXPRESSION_CATEGORY:
        raise ValueError(f"未知表情 {name}，可选 {EXPRESSIONS}")
    c = new_canvas()
    lx, rx = WIDTH // 2 - EYE_DX, WIDTH // 2 + EYE_DX

    if name == "normal":
        disc(c, lx, EYE_CY, EYE_R)
        disc(c, rx, EYE_CY, EYE_R)
        curve(c, WIDTH // 2, MOUTH_TOP + 1, 38, 4, down=True, thick=2)

    elif name == "happy":
        # ^ ^ 眼
        for cx in (lx, rx):
            for k in range(2):
                line(c, cx - 7, EYE_CY + 4 + k, cx, EYE_CY - 3 + k)
                line(c, cx, EYE_CY - 3 + k, cx + 7, EYE_CY + 4 + k)
        # 大笑（压低起点，别顶到眼睛）
        curve(c, WIDTH // 2, MOUTH_TOP - 1, 52, 6, down=True, thick=3)

    elif name == "sad":
        disc(c, lx, EYE_CY, EYE_R)
        disc(c, rx, EYE_CY, EYE_R)
        # 八字眉（外端下垂）
        brow(c, lx, BROW_CY, -2)
        brow(c, rx, BROW_CY, 2)
        # 撇嘴（∩）
        curve(c, WIDTH // 2, MOUTH_TOP + 6, 34, 4, down=False, thick=2)

    elif name == "angry":
        disc(c, lx, EYE_CY, EYE_R)
        disc(c, rx, EYE_CY, EYE_R)
        # 倒八字眉（内端下压）
        brow(c, lx, BROW_CY + 1, 2)
        brow(c, rx, BROW_CY + 1, -2)
        # 咬牙：撇嘴 + 一条横线
        curve(c, WIDTH // 2, MOUTH_TOP + 6, 32, 3, down=False, thick=2)
        line(c, WIDTH // 2 - 13, MOUTH_TOP + 6, WIDTH // 2 + 13, MOUTH_TOP + 6)

    elif name == "thinking":
        disc(c, lx, EYE_CY, EYE_R)
        for k in range(2):                      # 右眼眯成横线
            line(c, rx - 6, EYE_CY + k, rx + 6, EYE_CY + k)
        # 一边嘴角翘起
        curve(c, WIDTH // 2 - 10, MOUTH_TOP + 1, 24, 4, down=True, thick=2)
        for i in range(3):                      # 省略号
            disc(c, WIDTH // 2 + 24 + i * 9, MOUTH_TOP + 2, 1)

    elif name == "celebrate":
        sparkle(c, lx, EYE_CY, 6)
        sparkle(c, rx, EYE_CY, 6)
        # 张嘴大笑（双层曲线做出"开口"感）
        curve(c, WIDTH // 2, MOUTH_TOP - 1, 50, 6, down=True, thick=2)
        curve(c, WIDTH // 2, MOUTH_TOP + 2, 36, 4, down=True, thick=2)
        sparkle(c, 34, 8, 3)
        sparkle(c, WIDTH - 34, 20, 3)

    return c


def all_faces():
    return {name: draw_face(name) for name in EXPRESSIONS}


def contact_sheet(path=None, scale: int = 3):
    """把 6 个表情拼成一张对比图。"""
    from PIL import Image
    faces = all_faces()
    sheet = Image.new("L", (WIDTH, (HEIGHT + 3) * len(faces)), 0)
    for i, name in enumerate(EXPRESSIONS):
        sheet.paste(canvas_to_image(faces[name]), (0, i * (HEIGHT + 3)))
    if scale > 1:
        sheet = sheet.resize((WIDTH * scale, sheet.height * scale), Image.NEAREST)
    if path:
        sheet.save(path)
    return sheet
