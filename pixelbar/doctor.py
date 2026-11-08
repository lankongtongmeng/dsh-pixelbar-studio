#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动预检（doctor）：把「能不能用」拆成可逐项定位的检查。

设计原则：**每一项都必须给出"怎么修"**。只报错不给修法等于没报。
分三级：``ok`` 可用 / ``warn`` 能用但有缺（多为可选功能）/ ``fail`` 挡路。
"""
from __future__ import annotations

import pathlib
import sys

from . import render as rn

OK, WARN, FAIL = "ok", "warn", "fail"
_ICON = {OK: "[OK ]", WARN: "[警告]", FAIL: "[失败]"}

ROOT = pathlib.Path(__file__).resolve().parent.parent


class Report:
    def __init__(self):
        self.items: list[tuple[str, str, str, str]] = []

    def add(self, level: str, name: str, detail: str = "", fix: str = ""):
        self.items.append((level, name, detail, fix))

    @property
    def worst(self) -> str:
        for lv in (FAIL, WARN):
            if any(i[0] == lv for i in self.items):
                return lv
        return OK

    def render(self) -> str:
        lines = []
        for lv, name, detail, fix in self.items:
            lines.append(f"{_ICON[lv]} {name}" + (f"：{detail}" if detail else ""))
            if fix and lv != OK:
                lines.append(f"       ↳ {fix}")
        n_fail = sum(1 for i in self.items if i[0] == FAIL)
        n_warn = sum(1 for i in self.items if i[0] == WARN)
        lines.append("")
        if n_fail:
            lines.append(f"结论：{n_fail} 项挡路、{n_warn} 项有缺 —— "
                         "先按上面的 ↳ 修掉失败项。")
        elif n_warn:
            lines.append(f"结论：可以正常使用，{n_warn} 项可选功能缺失。")
        else:
            lines.append("结论：全部就绪。")
        return "\n".join(lines)


# ---------------------------------------------------------------- 各项检查

def check_python(rep: Report) -> None:
    v = sys.version_info
    ok = v >= (3, 10)
    rep.add(OK if ok else FAIL, "Python 版本",
            f"{v.major}.{v.minor}.{v.micro}",
            "需要 3.10+（代码用了 `int | None` 这类新语法）")


def _try_import(mod: str) -> tuple[bool, str]:
    try:
        m = __import__(mod)
        return True, getattr(m, "__version__", "")
    except Exception as e:                                    # noqa: BLE001
        return False, f"{type(e).__name__}"


def check_deps(rep: Report) -> None:
    ok, ver = _try_import("hid")
    rep.add(OK if ok else FAIL, "hidapi（设备通信）", ver or "未安装",
            "python -m pip install --user hidapi（注意不是 PyPI 上的 `hid` 包）")
    ok, ver = _try_import("PIL")
    rep.add(OK if ok else FAIL, "Pillow（绘图/转码）", ver or "未安装",
            "python -m pip install --user pillow")
    for mod, why in (("sounddevice", "play"), ("soundfile", "play")):
        ok, ver = _try_import(mod)
        rep.add(OK if ok else WARN, f"{mod}（{why} 命令用）", ver or "未安装",
                "python -m pip install --user sounddevice soundfile")


def check_fonts(rep: Report) -> None:
    for path, why in ((rn.CJK_FONT, "中文点阵"),
                      (rn.MONO_FONT, "等宽 ASCII 点阵")):
        p = pathlib.Path(path)
        rep.add(OK if p.exists() else WARN, f"字体 {p.name}（{why}）",
                "存在" if p.exists() else f"缺 {path}",
                "Windows 自带该字体；换机器若缺失，改 render.py 里的字体路径")


def check_assets(rep: Report) -> None:
    from . import chars as ch
    try:
        lib = ch.Library()
    except Exception as e:                                    # noqa: BLE001
        rep.add(FAIL, "动画配方 anims.json", f"{type(e).__name__}: {e}",
                "检查 pixelbar/anims.json 是否被改坏（JSON 语法）")
        return
    rep.add(OK, "动画配方 anims.json", f"{len(lib.anims)} 个动画、"
            f"{len(lib.sheets)} 张角色表")

    have = lib.available()
    miss = [n for n in lib.sheets if n not in have]
    if not have:
        rep.add(FAIL, "角色表素材", "一张都没有",
                f"把 Pepper&Carrot 角色表放进 {ch.OGA_DIR}（见 docs/WORKFLOW.md §2）")
    elif miss:
        rep.add(WARN, "角色表素材", f"有 {len(have)} 张，缺 {miss}",
                f"缺的表只影响用到它的动画；补进 {ch.OGA_DIR} 即可")
    else:
        rep.add(OK, "角色表素材", f"{len(have)} 张齐全")

    broken = [n for n in lib.anims if lib.missing_sheets(n)]
    if broken:
        rep.add(WARN, "动画可用性", f"{broken} 引用了缺失的角色表",
                "补素材，或从 anims.json 里删掉这些动画")


def check_fixture(rep: Report) -> None:
    from .cli import FIXTURE
    rep.add(OK if FIXTURE.exists() else WARN, "官方抓包 fixtures",
            "存在" if FIXTURE.exists() else f"缺 {FIXTURE}",
            "缺了只影响 selftest 里『逐字节复现官方抓包』那几项")


def check_device(rep: Report) -> None:
    from . import protocol as px
    try:
        info = px.find_device()
    except Exception as e:                                    # noqa: BLE001
        rep.add(FAIL, "设备枚举", f"{type(e).__name__}: {e}", "先装 hidapi")
        return
    if not info:
        rep.add(FAIL, "设备", "没枚举到控制接口",
                "① 用 USB-C 数据线（纯充电线不行）；"
                "② 蓝牙模式不枚举 HID，必须插 USB；"
                "③ TempoHub 可能占着设备，先关掉")
        return
    rep.add(OK, "设备", f"{info.get('product_string')} "
            f"(VID 0x{info['vendor_id']:04X}/PID 0x{info['product_id']:04X})")
    # 链路体检：固件卡死时会持续刷 ACK
    try:
        with px.Device(info) as dev:
            from . import wire as wr
            wr.assert_link_healthy(dev)
        rep.add(OK, "设备链路", "正常")
    except RuntimeError as e:
        rep.add(FAIL, "设备链路", str(e).splitlines()[0],
                "断电重启设备（拔插 USB-C 数据线或关机重开）")
    except Exception as e:                                    # noqa: BLE001
        rep.add(WARN, "设备链路", f"{type(e).__name__}: {e}",
                "能枚举但打不开，可能被别的程序占用")


CHECKS = (check_python, check_deps, check_fonts, check_assets,
          check_fixture, check_device)


def run(with_device: bool = True) -> Report:
    rep = Report()
    for fn in CHECKS:
        if fn is check_device and not with_device:
            continue
        try:
            fn(rep)
        except Exception as e:                                # noqa: BLE001
            rep.add(FAIL, fn.__name__, f"{type(e).__name__}: {e}", "内部错误")
    return rep
