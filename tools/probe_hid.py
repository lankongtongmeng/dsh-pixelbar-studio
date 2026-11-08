#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小化设备探针：分步打印，定位到底卡在哪一步（枚举/打开/写/读）。"""
from __future__ import annotations

import sys
import time

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

log("import hid")
import hid  # noqa: E402
log(f"hid ok, version={getattr(hid, '__version__', '?')}")

VID, PID, IFACE, UP, U = 0x2D99, 0xA106, 4, 0xFF14, 1

log("enumerate")
try:
    devs = hid.enumerate()
    log(f"enumerate ok, {len(devs)} devices")
except Exception as e:
    log(f"enumerate FAIL {type(e).__name__}: {e}")
    raise SystemExit(1)

target = None
for d in devs:
    if (d.get("vendor_id") == VID and d.get("product_id") == PID
            and d.get("interface_number") == IFACE
            and d.get("usage_page") == UP and d.get("usage") == U):
        target = d
        break
log(f"target = {'FOUND' if target else 'NOT FOUND'}")
if not target:
    for d in devs:
        if d.get("vendor_id") == VID and d.get("product_id") == PID:
            log(f"  same VID/PID: iface={d.get('interface_number')} "
                f"up={d.get('usage_page'):#06x} u={d.get('usage')}")
    raise SystemExit(2)

log("open_path")
try:
    h = hid.device()
    h.open_path(target["path"])
    log("open ok")
except Exception as e:
    log(f"open FAIL {type(e).__name__}: {e}")
    raise SystemExit(3)

log("set_nonblocking")
h.set_nonblocking(1)
log("ok")

log("read(200ms) 残留")
try:
    r = h.read(64, timeout_ms=200)
    log(f"read -> {bytes(r).hex(' ') if r else None}")
except Exception as e:
    log(f"read FAIL {type(e).__name__}: {e}")

log("write status frame (0x66)")
frame = bytes([0xAA, 0xEC, 0x66, 0x00, 0x00]) + bytes(59)
try:
    n = h.write(frame)
    log(f"write -> {n}")
except Exception as e:
    log(f"write FAIL {type(e).__name__}: {e}")

log("read 1s")
try:
    r = h.read(64, timeout_ms=1000)
    log(f"read -> {bytes(r).hex(' ') if r else None}")
except Exception as e:
    log(f"read FAIL {type(e).__name__}: {e}")

h.close()
log("closed, done")
