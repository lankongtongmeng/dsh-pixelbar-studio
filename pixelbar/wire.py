#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""0x17 位图上传的**线上格式**（1064 字节）编解码与上传时序。

线上格式（由 TempoHub 官方抓包逐字节证实）::

    1064 字节 = 8 条 133 字节记录
    每条 = 5 字节头 `T 00 NN XX XX` + 128 字节图像数据

      T     = 场景类别（game 01 / work 02 / study 03 / cat 04），
              也等于上传前 EF 帧的第 7 字节
      NN    = 记录序号 0..7，**多图上传时全局连续**（两张图为 00-07 与 08-0f）
      XX XX = 每场景值 / 帧间隔（抓包见过 0064 / 0030 / ffff）

与 TempoHub **本地 .bin** 的区别（这是此前错位的根因）::

    本地 .bin : 1040 = [16 字节全局头][1024 payload]
    线上 blob : 1064 = [5B头+128B] x 8

两者 payload 位布局**完全相同**，仅容器不同。把本地 1040 直接当线上格式发送，
设备按 133 字节记录解析，第 i 条 128 列块会漂移 ``5i-15`` 字节
（-15/-10/-5/0/+5/+10/+15/+20），症状即"粗图案看着对、细线小字全毁、每块各自偏移"。

payload 位布局::

    payload[(row // 8) * 256 + col] |= 1 << (row % 8)

已验证：对 ethan71950701/PixelBar-Display-Hook 的 3 组官方抓包
（capture 20 / 21 / 23）逐字节复现一致。
"""
from __future__ import annotations

import time

from . import protocol as px

WIDTH, HEIGHT = 256, 32
PAYLOAD_BYTES = (HEIGHT // 8) * WIDTH          # 1024
RECORD_DATA = 128
RECORD_HEADER = 5
RECORDS = PAYLOAD_BYTES // RECORD_DATA         # 8
WIRE_BYTES = RECORDS * (RECORD_HEADER + RECORD_DATA)   # 1064
MAX_FRAMES = 20                                # 槽位容量实测上限（21280 字节）

CHUNK_SIZE = 50                                # 设备 ready 回包宣告的块大小
DEFAULT_DELAY = 0x0064                         # 帧间隔（XX XX），100ms
SETTLE_AFTER_UPLOAD = 2.5                      # 上传后等固件提交完 flash 再切显示

# 各场景的用户图片槽位（wafer 在 A160 上抓到的值；A106 实测 option=0 可用）
SLOT_OPTION_A160 = {2: 10, 3: 9, 4: 3, 5: 0, 6: 0, 7: 15}


# ---------------------------------------------------------------- 位布局

def encode_payload(canvas) -> bytes:
    """画布（32 行 x 256 列，非 0 即亮）-> 1024 字节 payload。"""
    payload = bytearray(PAYLOAD_BYTES)
    for y in range(HEIGHT):
        row = canvas[y]
        for x in range(WIDTH):
            if row[x]:
                payload[(y // 8) * WIDTH + x] |= 1 << (y % 8)
    return bytes(payload)


def decode_payload(payload: bytes):
    """1024 字节 payload -> 画布。"""
    canvas = [[0] * WIDTH for _ in range(HEIGHT)]
    for y in range(HEIGHT):
        for x in range(WIDTH):
            idx = (y // 8) * WIDTH + x
            if idx < len(payload) and (payload[idx] >> (y % 8)) & 1:
                canvas[y][x] = 1
    return canvas


def payload_from_image(img) -> bytes:
    """PIL 图像（1 位或灰度，非 0 即亮）-> payload。"""
    im = img.convert("1")
    p = im.load()
    payload = bytearray(PAYLOAD_BYTES)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if p[x, y]:
                payload[(y // 8) * WIDTH + x] |= 1 << (y % 8)
    return bytes(payload)


def image_from_payload(payload: bytes, scale: int = 1):
    """payload -> PIL 灰度图（便于预览）。"""
    from PIL import Image
    canvas = decode_payload(payload)
    img = Image.new("L", (WIDTH, HEIGHT), 0)
    p = img.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if canvas[y][x]:
                p[x, y] = 255
    if scale > 1:
        img = img.resize((WIDTH * scale, HEIGHT * scale), Image.NEAREST)
    return img


# ---------------------------------------------------------------- 容器

def encode_wire(payload: bytes, category: int, delay: int = DEFAULT_DELAY,
                record_base: int = 0) -> bytes:
    """1024 payload -> 1064 线上 blob。"""
    if len(payload) != PAYLOAD_BYTES:
        raise ValueError(f"payload 必须是 {PAYLOAD_BYTES} 字节，收到 {len(payload)}")
    out = bytearray()
    for i in range(RECORDS):
        out += bytes([category & 0xFF, 0x00, (record_base + i) & 0xFF,
                      (delay >> 8) & 0xFF, delay & 0xFF])
        out += payload[i * RECORD_DATA:(i + 1) * RECORD_DATA]
    assert len(out) == WIRE_BYTES
    return bytes(out)


def encode_wire_multi(payloads, category: int, delay: int = DEFAULT_DELAY) -> bytes:
    """多张图 -> 一个 blob（记录序号跨图连续，即设备的多帧动画格式）。"""
    if len(payloads) > MAX_FRAMES:
        raise ValueError(f"最多 {MAX_FRAMES} 帧（槽位容量上限），收到 {len(payloads)}")
    return b"".join(encode_wire(p, category, delay, record_base=k * RECORDS)
                    for k, p in enumerate(payloads))


def decode_wire(blob: bytes, record_base: int = 0, strict: bool = False) -> bytes:
    """1064 blob -> 1024 payload。strict=True 时记录头异常抛错。"""
    payload = bytearray()
    n = len(blob) // (RECORD_HEADER + RECORD_DATA)
    for i in range(n):
        off = i * (RECORD_HEADER + RECORD_DATA)
        hdr = blob[off:off + RECORD_HEADER]
        expect = (record_base + i) & 0xFF
        if hdr[1] != 0 or hdr[2] != expect:
            msg = f"记录 {i} 头异常 {hdr.hex(' ')}（期望序号 {expect:02x}）"
            if strict:
                raise ValueError(msg)
            print(f"  警告：{msg}")
        payload += blob[off + RECORD_HEADER:off + RECORD_HEADER + RECORD_DATA]
    return bytes(payload)


def decode_wire_multi(blob: bytes) -> list[bytes]:
    """1064*N blob -> N 张 payload。"""
    return [decode_wire(blob[k * WIRE_BYTES:(k + 1) * WIRE_BYTES],
                        record_base=k * RECORDS)
            for k in range(len(blob) // WIRE_BYTES)]


# ---------------------------------------------------------------- 上传时序

def _read_state(dev, timeout: float = 5.0, accept=None, seq=None):
    """读 0x17 回包。

    设备在上传结束后仍会**持续吐残留 ACK**（连续推多个动画时表现为下一次 start
    收到 `00 03 00 NN`），所以这里必须能"只认想要的那个状态"，并且对数据 ACK
    校验块序号 —— 否则残留 ACK 会被当成本次握手成功，后续全部错位。

    ``accept``: 只接受这些 state；``seq``: 只接受该块序号的数据 ACK。
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        raw = dev.read(100)
        parsed = px.parse_frame(raw) if raw else None
        if not parsed or parsed[0] != px.CMD_PIXEL_FILE:
            continue
        payload = parsed[1]
        if not payload:
            continue
        state = payload[1] if len(payload) > 1 else None
        if accept is not None and state not in accept:
            continue
        if seq is not None and state == px.STATE_ACK_NEXT:
            got = (payload[2] << 8) | payload[3] if len(payload) > 3 else None
            if got != seq:
                continue
        return payload
    return None


def upload_blob(dev: px.Device, blob: bytes, verbose: bool = True) -> bool:
    """按 0x17 时序上传一个 blob。

    时序（官方抓包实证）::

        start  host: 17 [00 00 <size_be32>]      设备: 00 01 00 32（块大小 50）
        data   host: 17 [00 02 <seq_be16> <..>]  设备: 00 03 <seq>（逐块 ACK）
        end    host: 17 [00 04]                  设备: 00 05
    """
    dev.drain()
    size = len(blob)

    # start：只认 STATE_READY（0x01），残留 ACK 直接跳过；超时则重发
    reply = None
    for attempt in range(5):
        dev.drain()
        dev.send(px.CMD_PIXEL_FILE,
                 bytes([0x00, px.STATE_RECEIVE]) + size.to_bytes(4, "big"))
        reply = _read_state(dev, 2.5, accept={px.STATE_READY})
        if reply is not None:
            break
        if verbose:
            print(f"  start 第 {attempt + 1} 次未就绪，重试")
        time.sleep(0.5 * (attempt + 1))
    if reply is None:
        raise RuntimeError("start 无响应（TempoHub 是否占用设备？）")
    chunk = CHUNK_SIZE
    if len(reply) > 3:
        req = (reply[2] << 8) | reply[3]
        if 0 < req < chunk:
            chunk = req
    if verbose:
        print(f"  设备就绪，块大小 {chunk}，共 {size} 字节")

    # data
    offset, index, retries = 0, 0, 0
    while offset < size:
        piece = blob[offset:offset + chunk]
        dev.send(px.CMD_PIXEL_FILE,
                 bytes([0x00, px.STATE_SEND_DATA]) + index.to_bytes(2, "big") + piece)
        reply = _read_state(dev, 5.0,
                            accept={px.STATE_ACK_NEXT, px.STATE_ACK_DONE},
                            seq=index)
        if reply is None:
            retries += 1
            if retries > 3:
                raise RuntimeError(f"第 {index} 块无 ACK")
            if verbose:
                print(f"  第 {index} 块超时，重试 {retries}/3")
            time.sleep(0.5 * retries)
            continue
        retries = 0
        offset += len(piece)
        index += 1
        if verbose and index % 40 == 0:
            print(f"  已发 {offset}/{size}")
        if reply[1] == px.STATE_ACK_DONE:
            if verbose:
                print(f"  已发 {offset}/{size}（设备提前确认完成）")
            return True
        continue

    # end
    dev.send(px.CMD_PIXEL_FILE, bytes([0x00, px.STATE_END]))
    for _ in range(6):
        reply = _read_state(dev, 2.0, accept={px.STATE_ACK_DONE})
        if reply is not None:
            if verbose:
                print("  传输完成")
            return True
    if verbose:
        print("  已发完（未收到显式完成帧）")
    return True


def assert_link_healthy(dev, window: float = 0.5, spam_limit: int = 6) -> None:
    """上传前的链路体检：设备若卡在"持续刷 ACK"状态就立刻报错。

    实机踩坑：连续推多个动画时，设备可能在提交 flash 时卡死，之后**持续刷**
    ``2f bb ec 17 00 04 00 03 <seq>``（seq 每秒涨十几个），并且 HID 写返回 -1。
    此时继续发 start 只会让它更乱，必须断电重启（拔插 USB-C 数据线）。
    """
    dev.drain()
    deadline = time.monotonic() + window
    spam = 0
    sample = None
    while time.monotonic() < deadline:
        raw = dev.read(80)
        if not raw:
            continue
        parsed = px.parse_frame(raw)
        if parsed and parsed[0] == px.CMD_PIXEL_FILE:
            spam += 1
            sample = sample or px.hexs(parsed[1])
    if spam >= spam_limit:
        raise RuntimeError(
            f"设备固件卡在数据接收态：{window}s 内刷了 {spam} 个 0x17 回包"
            f"（样例 {sample}）。\n"
            "请断电重启设备（拔插 USB-C 数据线，或把音箱关机再开机）后重试。")


def select_upload_target(dev: px.Device, category: int, option: int,
                         rgb=px.DEFAULT_RGB, group: int = 0) -> None:
    """进入目标场景并选中要写入的槽位（0xEF 01 形式）。"""
    dev.send(px.CMD_PIXEL_SET, px.payload_scene(rgb, category))
    time.sleep(0.4)
    dev.send(px.CMD_PIXEL_SET, px.payload_scene_option(rgb, category, option, group))
    time.sleep(0.2)


def show_slot(dev: px.Device, category: int, option: int,
              rgb=px.DEFAULT_RGB) -> None:
    """显示已上传的槽位（0xEF 02 形式）。

    ``0xEF 01`` 只选上传目标（屏进"上传中"），必须用 ``0xEF 02`` + template
    才真正把槽位显示出来。
    """
    dev.send(px.CMD_PIXEL_SET, px.payload_scene(rgb, category, option))
    time.sleep(0.3)


def push_frames(dev: px.Device, payloads, category: int, option: int = 0,
                delay: int = DEFAULT_DELAY, settle: float = SETTLE_AFTER_UPLOAD,
                verbose: bool = True) -> int:
    """完整流程：体检 -> 选目标 -> 上传 -> 等提交 -> 切显示。返回帧数。"""
    blob = encode_wire_multi(payloads, category, delay)
    if verbose:
        print(f"{len(payloads)} 帧 -> {len(blob)} 字节（{len(payloads)*RECORDS} 条记录），"
              f"类别 {category}/槽位 {option}，帧间隔 {delay}ms")
    assert_link_healthy(dev)
    select_upload_target(dev, category, option)
    upload_blob(dev, blob, verbose=verbose)
    if settle:
        time.sleep(settle)          # 固件异步提交 flash，切太早会显示"上传失败"
    show_slot(dev, category, option)
    return len(payloads)


def replay_frames(dev: px.Device, frames, verbose: bool = True) -> int:
    """原样回放一组抓包 OUT 帧（用于验证链路）。"""
    dev.drain()
    for idx, fr in enumerate(frames):
        dev.write(bytes(fr))
        time.sleep(0.03)
        reply = dev.read(60)
        if verbose and (idx < 2 or idx == len(frames) - 1 or fr[3] == px.CMD_PIXEL_FILE):
            r = px.hexs(reply[:10]) if reply else "(无回包)"
            print(f"  [{idx:2d}] cmd={fr[3]:02x} -> {r}")
    return len(frames)
