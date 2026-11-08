#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音频播放：把 PixelBar 当声卡用。

PixelBar 走 USB 声卡模式时是一个标准输出设备，直接 `sounddevice` 播放即可。
注意 USB 声卡会以多个名字重复枚举（"扬声器 (2- 花再 Halo PixelBar)" 等），
蓝牙免提（Hands-Free）那条只有 1 个输出通道且音质差，要排除。
"""
from __future__ import annotations

import pathlib
import time

AUDIO_EXT = {".mp3", ".flac", ".m4a", ".wav", ".ogg", ".aac", ".opus", ".wma"}
NAME_HINT = "halo pixelbar"


def list_outputs():
    """[(设备号, 名字)]，仅输出设备。"""
    import sounddevice as sd
    return [(i, d["name"]) for i, d in enumerate(sd.query_devices())
            if d["max_output_channels"] > 0]


def find_outputs(hint: str = NAME_HINT):
    """按名字找候选输出设备，排除蓝牙免提（Hands-Free）。"""
    return [(i, n) for i, n in list_outputs()
            if hint.lower() in n.lower() and "hands-free" not in n.lower()]


def collect_files(paths):
    """目录递归收集音频文件；.txt 按播放列表读（每行一个路径）。

    用播放列表文件可以避开 shell 对中文/方括号文件名的转义问题。
    """
    out = []
    for p in paths:
        path = pathlib.Path(p)
        if path.is_dir():
            out += sorted(f for f in path.rglob("*")
                          if f.suffix.lower() in AUDIO_EXT)
        elif path.suffix.lower() == ".txt" and path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    q = pathlib.Path(line)
                    if q.is_file():
                        out.append(q)
                    else:
                        print(f"  播放列表项不存在：{line}")
        elif path.is_file():
            out.append(path)
        else:
            print(f"跳过（不存在）：{p}")
    return out


def _resample(data, src_rate, dst_rate):
    """线性重采样（避免依赖 scipy）。"""
    import numpy as np
    n = int(round(len(data) * dst_rate / src_rate))
    idx = np.linspace(0, len(data) - 1, n)
    return np.interp(idx, np.arange(len(data)), data[:, 0])[:, None].astype(data.dtype)


def _biquad_coeffs(kind, sr, freq, gain_db, q=0.707):
    """手写双二阶系数（RBJ cookbook），避免依赖 scipy。

    kind: 'highshelf' | 'lowshelf' | 'peaking'
    gain_db 为该段增益，正值提升、负值衰减。
    """
    import math
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * freq / sr
    cw, sw = math.cos(w0), math.sin(w0)
    alpha = sw / (2.0 * q)
    sqrtA = math.sqrt(A)
    two_sqrtA_alpha = 2.0 * sqrtA * alpha

    if kind == "highshelf":
        b0 = A * ((A + 1) + (A - 1) * cw + two_sqrtA_alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cw)
        b2 = A * ((A + 1) + (A - 1) * cw - two_sqrtA_alpha)
        a0 = (A + 1) - (A - 1) * cw + two_sqrtA_alpha
        a1 = 2 * ((A - 1) - (A + 1) * cw)
        a2 = (A + 1) - (A - 1) * cw - two_sqrtA_alpha
    elif kind == "lowshelf":
        b0 = A * ((A + 1) - (A - 1) * cw + two_sqrtA_alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cw)
        b2 = A * ((A + 1) - (A - 1) * cw - two_sqrtA_alpha)
        a0 = (A + 1) + (A - 1) * cw + two_sqrtA_alpha
        a1 = -2 * ((A - 1) + (A + 1) * cw)
        a2 = (A + 1) + (A - 1) * cw - two_sqrtA_alpha
    else:  # peaking
        b0 = 1 + alpha * A
        b1 = -2 * cw
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cw
        a2 = 1 - alpha / A
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _apply_biquad(data, coeffs):
    """逐通道用直接I型差分方程滤波。"""
    import numpy as np
    b0, b1, b2, a1, a2 = coeffs
    out = np.empty_like(data)
    for ch in range(data.shape[1]):
        x = data[:, ch].astype(np.float64)
        y = np.empty_like(x)
        x1 = x2 = y1 = y2 = 0.0
        for i in range(len(x)):
            xi = x[i]
            yi = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1 = x1, xi
            y2, y1 = y1, yi
            y[i] = yi
        out[:, ch] = y
    return out


def make_eq(sr, bass_db=0.0, treble_db=0.0, presence_db=0.0):
    """构造 EQ 链（返回可调用对象）。三段都接近 0 时返回 None（直通）。"""
    if abs(bass_db) < 0.01 and abs(treble_db) < 0.01 and abs(presence_db) < 0.01:
        return None
    stages = []
    if abs(bass_db) >= 0.01:
        stages.append(_biquad_coeffs("lowshelf", sr, 200.0, bass_db))
    if abs(presence_db) >= 0.01:
        stages.append(_biquad_coeffs("peaking", sr, 2500.0, presence_db, q=1.0))
    if abs(treble_db) >= 0.01:
        stages.append(_biquad_coeffs("highshelf", sr, 4000.0, treble_db))

    def eq(data):
        import numpy as np
        peak = float(np.max(np.abs(data))) or 1.0
        y = data.astype(np.float64)
        for c in stages:
            y = _apply_biquad(y, c)
        newpeak = float(np.max(np.abs(y))) or 1.0
        # 提升后可能过载，按峰值等比回退（保持相对 EQ 曲线不变）
        if newpeak > peak:
            y *= (peak / newpeak)
        return y.astype(np.float32)

    return eq


def play_files(files, device: int, on_track=None, repeat: int = 1,
               gap: float = 0.4, eq=None):
    """顺序播放。on_track(path, n, total) 在每首开始时回调。

    eq 为 make_eq() 返回的可调用对象（None 表示直通）。
    """
    import sounddevice as sd
    import soundfile as sf

    info = sd.query_devices(device)
    dev_rate = int(info["default_samplerate"])
    total = len(files) * repeat
    n = 0
    for _ in range(repeat):
        for f in files:
            n += 1
            if on_track:
                on_track(f, n, total)
            try:
                data, sr = sf.read(str(f), always_2d=True)
            except Exception as e:  # noqa: BLE001
                print(f"  读取失败 {f.name}: {e}")
                continue
            if sr != dev_rate:
                try:
                    data = _resample(data, sr, dev_rate)
                    sr = dev_rate
                except Exception:  # noqa: BLE001
                    pass
            if eq is not None:
                try:
                    data = eq(data)
                except Exception as e:  # noqa: BLE001
                    print(f"  EQ 处理失败 {f.name}: {e}")
            try:
                sd.play(data, sr, device=device)
                sd.wait()
            except Exception as e:  # noqa: BLE001
                print(f"  播放失败 {f.name}: {e}")
            time.sleep(gap)
