#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""花再 Halo PixelBar 控制工具 —— 命令行入口。

    python pixelbar.py selftest          # 离线自检（不连设备，先跑这个）
    python pixelbar.py status            # 查询设备
    python pixelbar.py text "你好"
    python pixelbar.py anim cat.gif      # 推 GIF 动画
    python pixelbar.py --help

依赖：python -m pip install --user hidapi pillow
"""
import sys

from pixelbar.cli import main

if __name__ == "__main__":
    sys.exit(main())
