#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看设备是否卡在持续刷 ACK 的状态，并试探写是否恢复。"""
from __future__ import annotations

import time

import hid

VID, PID, IFACE, UP, U = 0x2D99, 0xA106, 4, 0xFF14, 1


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


devs = hid.enumerate()
target = next(d for d in devs if d.get("vendor_id") == VID
              and d.get("product_id") == PID
              and d.get("interface_number") == IFACE
              and d.get("usage_page") == UP and d.get("usage") == U)
h = hid.device()
h.open_path(target["path"])
h.set_nonblocking(1)

log("读取 3 秒，统计回包")
seen = {}
t0 = time.time()
while time.time() - t0 < 3.0:
    r = h.read(64, timeout_ms=100)
    if r:
        b = bytes(r)
        key = b[:12].hex(" ")
        seen[key] = seen.get(key, 0) + 1
log(f"3 秒内收到 {sum(seen.values())} 帧，{len(seen)} 种前缀：")
for k, v in sorted(seen.items(), key=lambda kv: -kv[1])[:8]:
    log(f"   x{v:4d}  {k}")

log("再读 2 秒（看是否停止）")
t0 = time.time()
n = 0
while time.time() - t0 < 2.0:
    if h.read(64, timeout_ms=100):
        n += 1
log(f"2 秒内 {n} 帧")

log("试探写 0x66 状态查询 x3")
frame = bytes([0xAA, 0xEC, 0x66, 0x00, 0x00]) + bytes(59)
for i in range(3):
    try:
        w = h.write(frame)
    except Exception as e:
        w = f"EXC {type(e).__name__}: {e}"
    log(f"   write#{i} -> {w}")
    time.sleep(1.0)
    got = None
    for _ in range(5):
        r = h.read(64, timeout_ms=200)
        if r:
            got = bytes(r)[:12].hex(" ")
            break
    log(f"   读 -> {got}")

h.close()
log("done")
