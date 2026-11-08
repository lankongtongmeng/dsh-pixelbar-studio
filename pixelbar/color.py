# -*- coding: utf-8 -*-
"""像素屏颜色校准。

**这块屏的特性：R 通道增益偏低、B 偏强**，所以含红的颜色看起来偏青 / 偏紫
（默认屏色 ``#F0B4C8`` 直接发会明显偏青）。

校准值来自**目测实测**，不是从色彩空间算出来的。因此这里只做**精确匹配**：
命中锚点就替换，没命中就原样发——**不做插值**，因为插值出来的补偿值没有实测依据，
可能比不校准更糟。

⚠️ **校准只能应用一次。** 表里存在链式映射：黄 ``#FFFF00`` → ``#FF8800``，
而 ``#FF8800`` 本身又是橙的锚点 → ``#FF6000``。这是两次独立目测测量的自然结果
（各自对各自的目标色都正确），但意味着**不能对已经校准过的值再校准一次**，
否则会二次补偿。CLI 里校准只在设置颜色那一步做一次。

想自己重测：``pixelbar calib --card`` 把标准色卡轮流推到屏上，和电脑屏幕对比，
再改本文件的 ``CALIBRATION``。
"""
from __future__ import annotations

# 目标色（大写 hex） -> 补偿色（真正发到屏上的值）
#
# 来源：SilverlingFox/dsh-pixelbar（MIT）2026-08-01 目测校准，本项目沿用并在此注明。
# 逐条含义（"目标色: 屏上表现 → 补偿动作"）：
CALIBRATION: dict[str, str] = {
    "#FF0000": "#FF0303",  # 红: 偏深 → 微提亮
    "#00FF00": "#03FF03",  # 绿: 偏深 → 微提亮
    "#0000FF": "#0000FF",  # 蓝: 准，不动
    "#00FFFF": "#00FFD0",  # 青: 偏蓝 → 减 B
    "#FFFF00": "#FF8800",  # 黄: 直接发黄会偏绿 → 用 #FF8800 显示效果最像目标黄
    "#FF00FF": "#FF00D0",  # 品红: 偏紫 → 减 B
    "#F0B4C8": "#FF6080",  # 默认粉: 偏青 → R 拉满压 G/B（接近屏极限）
    "#FF8800": "#FF6000",  # 橙: 偏黄 → 减 G
    "#66AFFF": "#80C0FF",  # 天蓝: 偏深 → 提亮
    # 白色 #FFFFFF 故意不列：原校准者不用白色，未测
}

SOURCE = "SilverlingFox/dsh-pixelbar (MIT) · 2026-08-01 目测校准"

# 色卡：用于目测重校准。先看标准色，再看屏上实际颜色，凭偏差改 CALIBRATION。
COLOR_CARD: list[tuple[str, str]] = [
    ("纯红", "#FF0000"),
    ("纯绿", "#00FF00"),
    ("纯蓝", "#0000FF"),
    ("纯白", "#FFFFFF"),
    ("青色", "#00FFFF"),
    ("黄色", "#FFFF00"),
    ("品红", "#FF00FF"),
    ("默认粉", "#F0B4C8"),
    ("橙色", "#FF8800"),
    ("天蓝", "#66AFFF"),
]


def normalize_hex(value: str) -> str:
    """``f0b4c8`` / ``#F0B4C8`` -> ``#F0B4C8``。"""
    s = str(value).strip().lstrip("#").upper()
    return "#" + s


def calibrate_hex(value: str) -> str:
    """校准 hex 颜色。没命中锚点就原样返回。"""
    key = normalize_hex(value)
    return CALIBRATION.get(key, key)


def calibrate(rgb) -> tuple[int, int, int]:
    """校准 ``(r, g, b)``。没命中锚点就原样返回。"""
    r, g, b = (int(v) & 0xFF for v in rgb)
    out = calibrate_hex("#%02X%02X%02X" % (r, g, b))
    s = out.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def is_anchor(rgb) -> bool:
    """这个颜色有没有对应的校准锚点。"""
    r, g, b = (int(v) & 0xFF for v in rgb)
    return ("#%02X%02X%02X" % (r, g, b)) in CALIBRATION


def describe(rgb) -> str:
    """给 CLI 用的一句话说明。"""
    src = "#%02X%02X%02X" % tuple(int(v) & 0xFF for v in rgb)
    dst = calibrate(rgb)
    if tuple(int(v) & 0xFF for v in rgb) == dst:
        if is_anchor(rgb):
            return f"{src}（校准表里就是它本身，无需补偿）"
        return f"{src}（无对应锚点，原样发送；屏上会偏青/偏紫）"
    return f"{src} -> #%02X%02X%02X（已按校准表补偿）" % dst
