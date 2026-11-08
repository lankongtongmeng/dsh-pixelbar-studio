#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Halo PixelBar HID 协议层：设备发现、帧构造/解析、命令封装。

帧格式（64 字节，主机 -> 设备）::

    2E AA EC <cmd> <len_be16> <payload...> <checksum> <00 padding>

设备回包::

    2F BB EC <cmd> <len_be16> <payload...> <checksum> <00 padding>

``checksum = sum(帧[1:payload_end]) & 0xFF``（不含 report ID 0x2E/0x2F）。

本文件所有帧构造均已与本机实机、社区独立实现（halo-pixelbar-mcp、
claude-edifier-pixelbar-usage、traceless929/PixelBar 抓包）交叉校验。
"""
from __future__ import annotations

import time

try:
    import hid  # pip install hidapi
except ImportError:  # pragma: no cover
    hid = None

# ---------------------------------------------------------------- 设备标识

VID, PID = 0x2D99, 0xA106
IFACE, USAGE_PAGE, USAGE = 4, 0xFF14, 1

PACKET_LEN = 64
MAX_PAYLOAD = 57                      # 64 - 6(头) - 1(校验)
MAGIC = (0x2E, 0xAA, 0xEC)            # 主机 -> 设备
MAGIC_RESP = (0x2F, 0xBB, 0xEC)       # 设备 -> 主机

# ---------------------------------------------------------------- 命令号

CMD_AMBIENT_GET, CMD_AMBIENT_SET = 0x6A, 0x6B
CMD_VOLUME_GET, CMD_VOLUME_SET = 0x66, 0x67
CMD_EQ_GET, CMD_EQ_SET = 0xD5, 0xC4
CMD_TEXT_GET, CMD_TEXT_SET = 0xE7, 0xE8
CMD_PIXEL_GET, CMD_PIXEL_SET = 0xEE, 0xEF
CMD_PIXEL_FILE = 0x17                 # 位图/资源上传

# 0x17 子状态（payload 第 2 字节）
# 注意方向：0x00/0x02/0x04 是**主机发**的值，0x01/0x03/0x05 是**设备回**的值。
STATE_RECEIVE = 0x00                  # 主机 start：告知总长
STATE_READY = 0x01                    # 设备回 start：就绪，并给出块大小
STATE_SEND_DATA = 0x02                # 主机 data：分块
STATE_ACK_NEXT = 0x03                 # 设备回：继续发下一块
STATE_END = 0x04                      # 主机 end：收尾
STATE_ACK_DONE = 0x05                 # 设备回：完成

# ---------------------------------------------------------------- 取值表

DEFAULT_RGB = (0xF0, 0xB4, 0xC8)

# 屏幕场景类别（0 = 时钟走单独形式）
SCENES = {"clock": 0, "game": 1, "work": 2, "read": 3, "cats": 4,
          "dogs": 5, "memes": 6, "cyber": 7, "waves": 8}
SCENE_NAMES = {v: k for k, v in SCENES.items()}

ALIGN = {"left": 0, "center": 1, "right": 2, "justify": 3}

EFFECTS = {"breathing": 1, "color_tide": 2, "static": 3,
           "ripple": 4, "flow": 5, "dynamic": 6}
BRIGHTNESS = {"low": 0x14, "medium": 0x28, "high": 0x3C}

TEXT_LIMIT_CHARS, TEXT_LIMIT_BYTES = 16, 48

CLOCK_STYLES = 11                     # 0x0000 ~ 0x000A
SPECTRUM_BASE = 0x0800                # 0x0800 ~ 0x0803


# ---------------------------------------------------------------- 帧构造

def build_frame(cmd: int, payload: bytes = b"") -> bytes:
    """构造 64 字节主机请求帧。"""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload {len(payload)} 字节超过上限 {MAX_PAYLOAD}")
    body = bytearray([*MAGIC, cmd, (len(payload) >> 8) & 0xFF, len(payload) & 0xFF])
    body.extend(payload)
    body.append(sum(body[1:]) & 0xFF)
    return bytes(body) + bytes(PACKET_LEN - len(body))


def parse_frame(raw) -> tuple[int, bytes] | None:
    """解析设备回包 -> (cmd, payload)；不是合法回包则 None。"""
    if not raw:
        return None
    b = bytes(int(x) & 0xFF for x in raw)
    if len(b) < 6 or tuple(b[:3]) != MAGIC_RESP:
        return None
    length = (b[4] << 8) | b[5]
    return b[3], b[6:6 + length]


# ---------------------------------------------------------------- 载荷构造

def payload_text(text: str, color: int = 0) -> bytes:
    """文本载荷：``00 <n> <utf8...>``。

    **byte4 必须为 0x00**：它与 byte5 组成通用帧长度字段，填非 0 会让设备按
    256+ 字节解析一个 64 字节包。2026-11-08 实机复现 byte4=0x01 导致 USB 掉线，
    须断电重启。HaloLyricSync 声称的"颜色索引 0-6"是错的。
    """
    if color:
        raise ValueError("文本帧 byte4 必须为 0x00（见 docstring），非 0 会导致设备掉线")
    raw = text.encode("utf-8")
    return bytes([0x00, len(raw)]) + raw


def payload_scene(rgb, category: int, template: int = 0xFF) -> bytes:
    """场景类别包：``02 RGB 00 01 <cat> <tpl> FF``。"""
    return bytes([0x02, rgb[0], rgb[1], rgb[2], 0x00, 0x01,
                  category & 0xFF, template & 0xFF, 0xFF])


def payload_scene_option(rgb, category: int, option: int, group: int = 0) -> bytes:
    """场景选项包：``01 RGB <group> 01 <cat> <opt> FF``。

    注意：``0xEF 01`` 是"选上传目标"（屏进"上传中"），``0xEF 02``（payload_scene）
    才是"显示槽位"。
    """
    return bytes([0x01, rgb[0], rgb[1], rgb[2], group & 0xFF, 0x01,
                  category & 0xFF, option & 0xFF, 0xFF])


def payload_align(align: int, rgb=DEFAULT_RGB) -> bytes:
    """文本静态对齐：``01 RGB 00 02 00 <align> FF``。"""
    return bytes([0x01, rgb[0], rgb[1], rgb[2], 0x00, 0x02, 0x00, align & 0xFF, 0xFF])


def payload_scroll(direction: str, rgb=DEFAULT_RGB) -> bytes:
    """设备侧滚动：``01 RGB 00 02 01 <0|1> FF``（0=左到右，1=右到左）。"""
    idx = 0x01 if direction == "rtl" else 0x00
    return bytes([0x01, rgb[0], rgb[1], rgb[2], 0x00, 0x02, 0x01, idx, 0xFF])


def payload_pattern(index: int, rgb=DEFAULT_RGB) -> bytes:
    """图案/时钟/频谱：``01 RGB 00 01 <idx_hi> <idx_lo> FF``。

    时钟 0x0000~0x000A；频谱 0x0800~0x0803。
    """
    return bytes([0x01, rgb[0], rgb[1], rgb[2], 0x00, 0x01,
                  (index >> 8) & 0xFF, index & 0xFF, 0xFF])


def payload_screen_color(rgb, long_form: bool = True) -> bytes:
    """像素屏主题色：``03 RGB ...``。单色屏无逐像素彩色，这是整屏色调。"""
    if long_form:
        return bytes([0x03, rgb[0], rgb[1], rgb[2], 0x00, 0x00, 0xFF, 0xFF, 0xFF])
    return bytes([0x03, rgb[0], rgb[1], rgb[2]])


def payload_ambient(effect: int, rgb, brightness: int, speed: int) -> bytes:
    """氛围灯设置：``13 <effect> RGB <brightness> <speed>``。"""
    return bytes([0x13, effect & 0xFF, rgb[0], rgb[1], rgb[2],
                  brightness & 0xFF, max(1, min(10, speed))])


def payload_ambient_power(on: bool) -> bytes:
    """氛围灯总开关（第 7 项，开关编码在 B 通道）。"""
    return bytes([0x00, 0x00, 0x00, 0x00, 0x01 if on else 0x00, 0xFF, 0xFF])


def payload_volume(level: int) -> bytes:
    return bytes([level & 0xFF])


# ---------------------------------------------------------------- 设备 IO

def find_device():
    """返回控制接口的设备信息字典，未找到则 None。"""
    if hid is None:
        raise RuntimeError("缺少 hidapi：python -m pip install --user hidapi")
    for d in hid.enumerate():
        if (d.get("vendor_id") == VID and d.get("product_id") == PID
                and d.get("interface_number") == IFACE
                and d.get("usage_page") == USAGE_PAGE and d.get("usage") == USAGE):
            return d
    return None


class Device:
    """控制接口的 HID 会话。用作上下文管理器。"""

    def __init__(self, info=None, nonblocking: bool = True):
        if hid is None:
            raise RuntimeError("缺少 hidapi：python -m pip install --user hidapi")
        self.info = info or find_device()
        if self.info is None:
            raise RuntimeError(
                "未找到控制接口 VID_2D99 / PID_A106 / iface=4 / usage_page=0xFF14。\n"
                "请确认：① 用 USB-C 数据线（非纯充电线）连接；"
                "② 蓝牙模式下 HID 不枚举，必须走 USB。")
        self.dev = hid.device()
        self.dev.open_path(self.info["path"])
        self.dev.set_nonblocking(1 if nonblocking else 0)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- 基础读写 ---

    def write(self, frame: bytes, repeat: int = 1, gap: float = 0.03) -> int:
        """写帧。氛围灯等命令需连发多次才真正生效。"""
        n = 0
        for i in range(repeat):
            n = self.dev.write(frame)
            if i + 1 < repeat:
                time.sleep(gap)
        return n

    def read(self, timeout_ms: int = 80):
        try:
            r = self.dev.read(PACKET_LEN, timeout_ms=timeout_ms)
        except Exception:  # noqa: BLE001
            return None
        return bytes(r) if r else None

    def drain(self) -> None:
        """丢弃残留回包。"""
        while self.read(20):
            pass

    def read_frames(self, wait: float = 0.6) -> list[bytes]:
        """在 wait 秒内收齐一批回包。"""
        out, deadline = [], time.time() + wait
        while time.time() < deadline:
            r = self.read(80)
            if r:
                out.append(r)
                deadline = time.time() + 0.15
            else:
                time.sleep(0.01)
        return out

    def query(self, cmd: int, payload: bytes = b"", wait: float = 0.6):
        """发查询并返回该命令的首个 payload（无响应则 None）。"""
        self.write(build_frame(cmd, payload))
        for f in self.read_frames(wait):
            p = parse_frame(f)
            if p and p[0] == cmd:
                return p[1]
        return None

    def send(self, cmd: int, payload: bytes = b"", repeat: int = 1) -> None:
        self.write(build_frame(cmd, payload), repeat=repeat)

    def close(self) -> None:
        try:
            self.dev.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------- 高层操作

def show_text(dev: Device, text: str, align: str = "center",
              scroll: str | None = None) -> None:
    """显示文本。scroll 为 'ltr'/'rtl' 时用设备侧滚动。"""
    if scroll:
        dev.send(CMD_TEXT_SET, payload_text(text), repeat=2)
        dev.send(CMD_PIXEL_SET, payload_scroll(scroll), repeat=2)
    else:
        dev.send(CMD_PIXEL_SET, payload_align(ALIGN[align]))
        dev.send(CMD_TEXT_SET, payload_text(text))


def show_scene(dev: Device, scene: str, option: int = 0,
               rgb=DEFAULT_RGB, template: int = 0xFF) -> None:
    """切换内置场景（需发两包：category + option）。"""
    dev.send(CMD_PIXEL_SET, payload_scene(rgb, SCENES[scene], template))
    dev.send(CMD_PIXEL_SET, payload_scene_option(rgb, SCENES[scene], option))


def show_clock(dev: Device, n: int, rgb=DEFAULT_RGB) -> None:
    dev.send(CMD_PIXEL_SET, payload_pattern(max(1, min(CLOCK_STYLES, n)) - 1, rgb))


def show_spectrum(dev: Device, style: int, rgb=(0xC0, 0xFF, 0xF2)) -> None:
    dev.send(CMD_PIXEL_SET, payload_pattern(SPECTRUM_BASE | (style & 0x0F), rgb))


def set_screen_color(dev: Device, rgb) -> None:
    dev.send(CMD_PIXEL_SET, payload_screen_color(rgb))


def set_ambient(dev: Device, effect: str, rgb, brightness: str = "high",
                speed: int = 5) -> None:
    """设置氛围灯（连发 3 次才生效）。"""
    dev.send(CMD_AMBIENT_SET,
             payload_ambient(EFFECTS[effect], rgb, BRIGHTNESS[brightness], speed),
             repeat=3)


def set_ambient_power(dev: Device, on: bool) -> None:
    dev.send(CMD_AMBIENT_SET, payload_ambient_power(on), repeat=3)


def get_volume(dev: Device):
    """返回 (最大, 当前)，无响应则 None。"""
    p = dev.query(CMD_VOLUME_GET)
    return (p[0], p[1]) if p and len(p) >= 2 else None


def set_volume(dev: Device, level: int):
    cur = get_volume(dev)
    if not cur:
        return None
    level = max(0, min(cur[0], level))
    dev.send(CMD_VOLUME_SET, payload_volume(level), repeat=2)
    time.sleep(0.3)
    return get_volume(dev)


# EQ 音效模式（来自官方二进制 EqOptionType 枚举，0xC4 下发 / 0xD5 回读）
EQ_NAMES = {
    0: "音乐", 1: "纯净", 2: "电影", 3: "DIY", 4: "古典", 5: "复古",
    6: "游戏", 7: "流行", 8: "摇滚", 9: "动态", 10: "低音", 12: "发烧",
    13: "户外", 14: "监听", 15: "人声", 16: "DIY(无文件)", 17: "低音增强",
    18: "人声清晰", 19: "高频增强",
}
EQ_ALIASES = {
    "music": 0, "pure": 1, "movie": 2, "diy": 3, "classical": 4, "vintage": 5,
    "game": 6, "popular": 7, "rock": 8, "dynamic": 9, "bass": 10,
    "audiophile": 12, "outdoor": 13, "monitor": 14, "human": 15,
    "clear": 18, "clearvoice": 18, "high": 19, "highenhance": 19,
}


def get_eq(dev: Device):
    """回读当前 EQ 索引；无响应则 None。"""
    p = dev.query(CMD_EQ_GET)
    return p[0] if p else None


def set_eq(dev: Device, index: int):
    """设置 EQ 音效模式（0xC4 + 单字节索引），返回回读值。"""
    dev.send(CMD_EQ_SET, bytes([index & 0xFF]), repeat=3)
    time.sleep(0.3)
    return get_eq(dev)


def get_pixel_state(dev: Device) -> dict | None:
    """0xEE 回读 -> 配置字典。模式 1=场景 2=自定义文本 3=主题色。"""
    p = dev.query(CMD_PIXEL_GET)
    if not p or len(p) < 12:
        return None
    return {"raw": p, "rgb": (p[1], p[2], p[3]), "mode": p[5],
            "category": p[6], "option": p[7]}


def fit_text(text: str, max_chars: int = TEXT_LIMIT_CHARS,
             max_bytes: int = TEXT_LIMIT_BYTES) -> str:
    """裁剪到设备文本上限（16 字符 / 48 UTF-8 字节）。"""
    while text and len(text) > max_chars:
        text = text[:-1]
    while text and len(text.encode("utf-8")) > max_bytes:
        text = text[:-1]
    return text


def hexs(b) -> str:
    return " ".join(f"{x:02X}" for x in b) if b else "(空)"
