#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""二次元角色行走动画库 —— **声明式配方驱动**。

动画不是写死在代码里的，而是从 ``anims.json`` 读出来的：改 JSON 就能增删动画，
不用碰 Python。也可以用 ``--recipe 我的.json`` 追加/覆盖自己的配方。

配方结构::

    {
      "sheets": {                     # 角色表定义
        "pepper": {"file": "xxx.png", "cell": [24, 32],
                   "cols": 3, "rows": 4, "origin": [0, 0]}
      },
      "anims": {                      # 动画定义
        "cat": {"label": "小猫散步", "slot": 2, "style": "ground",
                "actors": [{"sheet": "carrot", "row": 1, "x": 116}]}
      }
    }

``actors`` 里每项 = 一个角色：``sheet`` 引用 sheets 的键，``row`` 选朝向
（0/2 正面、1/3 侧视），``x`` 是左边缘列，``flip`` 可水平翻转。
``slot`` 是烧到设备哪个 category（``null`` = 只在库里、不参与默认烧录）。

素材：**Pepper&Carrot 24x32 角色表**
* 来源：https://opengameart.org/content/24x32-peppercarrot-characters
* 作者：**David Revoy**（改编自其网络漫画 Pepper&Carrot 的线稿）
* 授权：**CC-BY 4.0 / CC-BY 3.0（须署名，不是 CC0）**
  —— 作者声明非商业用途可免署名，但仍应注明 David Revoy。

选它的理由：角色是**原生 24x32 像素画**，和 32 像素高的屏**等高、不需要缩放**，
不会糊；动漫画风；每行一个朝向、每列一个行走帧（3 帧循环）。
"""
from __future__ import annotations

import json
import pathlib

from . import render as rn
from . import sprite as sp

PKG_DIR = pathlib.Path(__file__).resolve().parent
OGA_DIR = PKG_DIR.parent / "gifs" / "oga"
RECIPE = PKG_DIR / "anims.json"

# 每行 3 个走姿；输出帧数取它的整数倍才能无缝循环（18 = 6 个完整走姿循环）
WALK_FRAMES = 18

# anims.json 缺失时的最小兜底（保证包永远可用）
_FALLBACK = {
    "sheets": {
        "pepper": {"file": "Pepper_publish..png"},
        "carrot": {"file": "carrot..png"},
        "coriander": {"file": "coriander_publish..png"},
        "saffron": {"file": "saffron_publish..png"},
        "shichimi": {"file": "shichimi_publish..png"},
    },
    "anims": {
        "cat": {"label": "小猫 Carrot 散步", "slot": 2, "style": "ground",
                "actors": [{"sheet": "carrot", "row": 1, "x": 116}]},
    },
}

# 署名信息（CC-BY 要求）：写进导出 GIF 的 comment，也供文档引用
CREDIT = ("Pepper&Carrot 24x32 characters by David Revoy, CC-BY 4.0 "
          "(opengameart.org/content/24x32-peppercarrot-characters)")


def _norm_sheet(name: str, spec: dict) -> dict:
    cell = spec.get("cell", [sp.CELL_W, sp.CELL_H])
    origin = spec.get("origin", [0, 0])
    return {
        "name": name,
        "path": OGA_DIR / spec["file"],
        "cell": tuple(cell),
        "cols": int(spec.get("cols", sp.COLS)),
        "rows": int(spec.get("rows", sp.ROWS)),
        "origin": tuple(origin),
    }


def load_recipe(*extra_paths) -> dict:
    """读内置配方，再按顺序合并 ``extra_paths``（后者覆盖前者）。"""
    data = {"sheets": dict(_FALLBACK["sheets"]),
            "anims": dict(_FALLBACK["anims"])}
    sources = [RECIPE, *[pathlib.Path(p) for p in extra_paths if p]]
    for p in sources:
        if not p or not pathlib.Path(p).exists():
            continue
        try:
            raw = json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
        except Exception as e:                                    # noqa: BLE001
            raise RuntimeError(f"配方文件读不了：{p}（{type(e).__name__}: {e}）")
        for key in ("sheets", "anims"):
            if isinstance(raw.get(key), dict):
                data[key].update(raw[key])
    data["sheets"] = {k: _norm_sheet(k, v) for k, v in data["sheets"].items()}
    return data


class Library:
    """一个配方加载出来的动画库。"""

    def __init__(self, *extra_paths):
        self.data = load_recipe(*extra_paths)
        self.sheets = self.data["sheets"]
        self.anims = self.data["anims"]

    # --- 查询 ---

    @property
    def names(self) -> list[str]:
        return list(self.anims)

    def slots(self) -> dict[str, int]:
        """参与默认烧录的动画 -> category。"""
        return {n: a["slot"] for n, a in self.anims.items()
                if a.get("slot") is not None}

    def slot_conflicts(self) -> dict[int, list[str]]:
        """一个 category 被多个动画占用 —— 会互相覆盖，必须报出来。"""
        used: dict[int, list[str]] = {}
        for n, s in self.slots().items():
            used.setdefault(s, []).append(n)
        return {s: ns for s, ns in used.items() if len(ns) > 1}

    def label(self, name: str) -> str:
        return self.anims[name].get("label", name)

    def available(self) -> list[str]:
        """本地已下载、可用的角色表名。"""
        return [n for n, s in self.sheets.items() if s["path"].exists()]

    def missing_sheets(self, name: str) -> list[str]:
        return [a["sheet"] for a in self.anims[name]["actors"]
                if a["sheet"] in self.sheets and not self.sheets[a["sheet"]]["path"].exists()]

    # --- 渲染 ---

    def grid(self, sheet: str):
        s = self.sheets[sheet]
        return sp.slice_sheet(s["path"], cell=s["cell"], cols=s["cols"],
                              rows=s["rows"], origin=s["origin"])

    def canvases(self, name: str, n_frames: int = WALK_FRAMES, ground: int = 29):
        """按动画名生成画布列表。"""
        if name not in self.anims:
            raise KeyError(f"没有动画 {name}，可选：{self.names}")
        spec = self.anims[name]
        actors = []
        for a in spec["actors"]:
            sh = self.sheets[a["sheet"]]
            actors.append({"sheet": self.grid(a["sheet"]), "row": a["row"],
                           "x": a.get("x"), "flip": a.get("flip", False),
                           "bob": a.get("bob", True)})
        return sp.walk_scene(actors, n_frames=n_frames, ground=ground,
                            style=spec.get("style", "ground"))

    def export_gif(self, name: str, path, frame_ms: int = 120,
                   n_frames: int = WALK_FRAMES):
        """导出成 GIF 文件（256x32 单色，无限循环）。

        导出的是**上屏后的真实点阵**，所以拿 GIF 看和看设备是同一份内容。
        会把 CC-BY 要求的署名写进 GIF 的 comment 段。
        """
        cs = self.canvases(name, n_frames=n_frames)
        frames = [rn.canvas_to_image(c) for c in cs]
        first, rest = frames[0], frames[1:]
        kw = dict(save_all=True, append_images=rest, duration=frame_ms,
                  loop=0, disposal=2, optimize=False)
        try:
            first.save(path, comment=CREDIT.encode("utf-8"), **kw)
        except TypeError:                      # 老版本 Pillow 不支持 comment
            first.save(path, **kw)
        return path


# ---------------------------------------------------------------- 模块级默认库
#
# 保留旧的模块级 API（SCENES / DEFAULT_SLOTS / canvases / ...），
# 让既有脚本与 CLI 不用改。

_DEFAULT = Library()

SCENES = _DEFAULT.anims
SHEETS = {k: v["path"].name for k, v in _DEFAULT.sheets.items()}
DEFAULT_SLOTS = _DEFAULT.slots()


def sheet_path(name: str) -> pathlib.Path:
    return _DEFAULT.sheets[name]["path"]


def available() -> list[str]:
    return _DEFAULT.available()


def canvases(name: str, n_frames: int = WALK_FRAMES, ground: int = 29):
    return _DEFAULT.canvases(name, n_frames=n_frames, ground=ground)


def export_gif(name: str, path, frame_ms: int = 120,
               n_frames: int = WALK_FRAMES):
    return _DEFAULT.export_gif(name, path, frame_ms=frame_ms,
                               n_frames=n_frames)
