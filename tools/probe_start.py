#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""0x17 start 握手的手工抓包：发 start，把收到的所有回包原样打出来。

用法::  python tools/probe_start.py [--cat 2]
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from pixelbar import protocol as px  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--cat", type=int, default=2)
ap.add_argument("--option", type=int, default=0)
ap.add_argument("--size", type=int, default=1064)
a = ap.parse_args()

with px.Device() as dev:
    print("已打开设备，先 dump 当前残留回包：")
    for i, f in enumerate(dev.read_frames(0.8)):
        print(f"   [{i}] {px.hexs(f)}  parsed={px.parse_frame(f)}")

    print(f"\n切到 category {a.cat} / option {a.option}")
    dev.send(px.CMD_PIXEL_SET, px.payload_scene(px.DEFAULT_RGB, a.cat))
    time.sleep(0.4)
    dev.send(px.CMD_PIXEL_SET,
             px.payload_scene_option(px.DEFAULT_RGB, a.cat, a.option, 0))
    time.sleep(0.3)
    for i, f in enumerate(dev.read_frames(0.6)):
        print(f"   [ef {i}] {px.hexs(f)}  parsed={px.parse_frame(f)}")

    print(f"\n发 start（size={a.size}）")
    dev.drain()
    dev.send(px.CMD_PIXEL_FILE,
             bytes([0x00, px.STATE_RECEIVE]) + a.size.to_bytes(4, "big"))
    frames = dev.read_frames(3.0)
    print(f"收到 {len(frames)} 个回包：")
    for i, f in enumerate(frames):
        p = px.parse_frame(f)
        print(f"   [{i}] raw={px.hexs(f)}")
        print(f"        parsed cmd={p[0]:#04x} payload={px.hexs(p[1]) if p else None}")
