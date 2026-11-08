#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐个切换动画并回读像素屏状态，确认 0xEF 切换真的落到对应 category。"""
from __future__ import annotations

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pixelbar import chars as ch  # noqa: E402
from pixelbar import protocol as px  # noqa: E402
from pixelbar import wire as wr  # noqa: E402

with px.Device() as dev:
    for name, cat in ch.DEFAULT_SLOTS.items():
        wr.show_slot(dev, cat, 0)
        time.sleep(0.8)
        st = px.get_pixel_state(dev)
        print(f"{name:8s} 期望 category={cat} -> 回读 {st}")
