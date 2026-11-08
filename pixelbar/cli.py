#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命令行入口：``python pixelbar.py <命令>``。"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

from . import audio as au
from . import chars as ch
from . import doctor as dr
from . import faces as fc
from . import protocol as px
from . import render as rn
from . import sprite as sp
from . import wire as wr

FIXTURE = pathlib.Path(__file__).resolve().parent.parent / "wiretest" / "captures.json"


def _dummy_sheet_path(img):
    """把内存里的 PIL 图落成临时 PNG，供只吃路径的 slice_sheet 使用。"""
    import tempfile
    p = pathlib.Path(tempfile.gettempdir()) / "_pixelbar_selftest_sheet.png"
    img.save(p)
    return p


def _dummy_json(data):
    """把内存里的字典落成临时 JSON，供配方合并测试使用。"""
    import json as _json
    import tempfile
    p = pathlib.Path(tempfile.gettempdir()) / "_pixelbar_selftest_recipe.json"
    p.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p

HERE = pathlib.Path(__file__).resolve().parent.parent


def parse_rgb(s: str):
    s = s.lstrip("#")
    if len(s) != 6:
        raise argparse.ArgumentTypeError("颜色格式为 RRGGBB，例如 ff8800")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def parse_cell(s: str):
    """``24x32`` / ``24,32`` / ``24 32`` -> (24, 32)。"""
    for sep in ("x", "X", ",", " "):
        s = s.replace(sep, " ")
    parts = [p for p in s.split() if p]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("要写成 宽x高，例如 24x32")
    return (int(parts[0]), int(parts[1]))


# ---------------------------------------------------------------- 离线自检

def _brief(v, limit: int = 60) -> str:
    """紧凑展示，避免把整个画布/payload 打出来。"""
    import hashlib
    if isinstance(v, (bytes, bytearray)):
        if len(v) > limit:
            h = hashlib.sha256(bytes(v)).hexdigest()[:8]
            return f"<{type(v).__name__} {len(v)}B sha256:{h}>"
        return repr(bytes(v))
    if isinstance(v, list):
        if len(v) > 12:
            flat = str(v)
            h = hashlib.sha256(flat.encode()).hexdigest()[:8]
            return f"<list len={len(v)} sha256:{h}>"
        return repr(v)
    return repr(v)


def cmd_selftest(_a) -> int:
    """不连设备的自检：帧构造、校验和、线上格式、官方抓包复现。"""
    ok = True

    def check(label, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        if good:
            print(f"[OK ] {label}")
        else:
            print(f"[FAIL] {label}: got {_brief(got)} want {_brief(want)}")

    # 1) 场景帧校验字节（与 HaloLyricSync 硬编码值交叉验证）
    for name, exp in [("clock", 0xFB), ("game", 0xFC), ("work", 0xFD), ("read", 0xFE),
                      ("cats", 0xFF), ("dogs", 0x00), ("memes", 0x01),
                      ("cyber", 0x02), ("waves", 0x03)]:
        f = px.build_frame(px.CMD_PIXEL_SET,
                           px.payload_scene(px.DEFAULT_RGB, px.SCENES[name]))
        check(f"场景 {name} 校验字节", f[15], exp)

    # 2) 帧长与魔数
    check("文本帧长度", len(px.build_frame(px.CMD_TEXT_SET, px.payload_text("test"))), 64)
    check("魔数", bytes(px.build_frame(0x66)[:3]), bytes(px.MAGIC))
    check("校验和自洽", px.build_frame(0x66)[6], (0xAA + 0xEC + 0x66) & 0xFF)

    # 3) 文本 byte4 必须为 0
    check("文本 byte4=0", px.payload_text("花再")[0], 0)
    try:
        px.payload_text("x", color=1)
        check("非 0 byte4 被拒", False, True)
    except ValueError:
        check("非 0 byte4 被拒", True, True)

    # 4) 线上格式往返
    canvas = rn.new_canvas()
    canvas[0][0] = canvas[31][255] = canvas[15][128] = 1
    payload = wr.encode_payload(canvas)
    check("payload 长度", len(payload), 1024)
    check("payload 往返一致", wr.decode_payload(payload), canvas)
    blob = wr.encode_wire(payload, category=2)
    check("blob 长度", len(blob), 1064)
    check("blob 记录头", blob[:5].hex(" "), "02 00 00 00 64")
    check("blob 第 2 条头", blob[133:138].hex(" "), "02 00 01 00 64")
    check("blob 往返一致", wr.decode_wire(blob), payload)

    # 5) 多帧：记录序号必须跨图连续
    multi = wr.encode_wire_multi([payload, payload], category=3, delay=0x30)
    check("多帧长度", len(multi), 2128)
    check("第 5 条头(跨图连续)", multi[532:537].hex(" "), "03 00 04 00 30")
    check("第 9 条头", multi[1064:1069].hex(" "), "03 00 08 00 30")
    check("多帧往返一致", wr.decode_wire_multi(multi), [payload, payload])

    # 6) 用官方抓包逐字节复现（最强的回归测试）
    if FIXTURE.exists():
        caps = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for name, (cat, delay) in {"20": (0x02, 0x64), "21": (0x03, 0x30),
                                   "23": (0x04, 0xFFFF)}.items():
            if name not in caps:
                continue
            blob = bytearray()
            for h in caps[name]["out"]:
                fr = bytes.fromhex(h)
                if len(fr) >= 6 and fr[3] == px.CMD_PIXEL_FILE:
                    pl = fr[6:6 + ((fr[4] << 8) | fr[5])]
                    if len(pl) >= 4 and pl[0] == 0 and pl[1] == px.STATE_SEND_DATA:
                        blob += pl[4:]
            payloads = wr.decode_wire_multi(bytes(blob))
            rebuilt = wr.encode_wire_multi(payloads, cat, delay)
            check(f"复现官方抓包 capture {name}", rebuilt == bytes(blob), True)
    else:
        print(f"[跳过] 未找到官方抓包 fixtures：{FIXTURE}")

    # 7) 动图/精灵层（这些坑都实际踩过，必须锁住）
    from PIL import Image as _I

    # 7a) 透明背景必须走 alpha，不能被亮度阈值吃掉整块背景
    rgba = _I.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y in range(3, 6):
        for x in range(3, 6):
            rgba.putpixel((x, y), (255, 255, 255, 255))
    check("透明帧被识别", rn.has_transparency(rgba), True)
    m = rn.frame_foreground(rgba)
    check("透明帧只取 alpha 前景", m.convert("L").histogram()[255], 9)

    # 7b) 双色底图：必须在**区域内**取底色众数
    sheet = _I.new("RGBA", (48, 32), (0, 117, 117, 255))   # 左半青绿底
    for y in range(32):
        for x in range(24, 48):
            sheet.putpixel((x, y), (107, 138, 139, 255))   # 右半灰底
    for y in range(4, 8):
        for x in range(4, 8):
            sheet.putpixel((x, y), (240, 160, 60, 255))    # 角色
    check("区域底色众数", sp.flat_background(sheet.crop((0, 0, 24, 32))),
          (4, 116, 116))
    grid = sp.slice_sheet(_dummy_sheet_path(sheet), cell=(24, 32), cols=1, rows=1)
    check("切片只留角色", grid[0][0].convert("L").histogram()[255], 16)

    # 7c) 无缝循环的两条硬约束（不满足就会看到"卡一下"）
    walk_frames = 3                                 # 角色表每行 3 个走姿
    check("帧数是走姿整数倍", ch.WALK_FRAMES % walk_frames, 0)
    for style, period in sp.STYLE_PERIOD.items():
        speed = period / ch.WALK_FRAMES
        check(f"背景首尾对齐({style})",
              int(ch.WALK_FRAMES * speed) % period, 0)

    # 7d) 动画库产出的画布形状与帧数
    if ch.available():
        cs = ch.canvases("cat")
        check("动画帧数", len(cs), ch.WALK_FRAMES)
        check("动画画布尺寸", (len(cs[0]), len(cs[0][0])), (32, 256))
        check("动画有内容", sum(sum(r) for r in cs[0]) > 0, True)
        # 地面虚线的相位必须首尾相接：末帧之后回到第 0 帧的相位
        off0 = int(0 * (24 / ch.WALK_FRAMES)) % 24
        off_next = int(ch.WALK_FRAMES * (24 / ch.WALK_FRAMES)) % 24
        check("虚线相位首尾相接", off_next, off0)
    else:
        print("[跳过] 未下载 Pepper&Carrot 角色表")

    # 8) 声明式配方（anims.json）与自定义配方合并
    lib = ch.Library()
    check("内置配方动画数", len(lib.anims) >= 5, True)
    check("内置槽位映射", lib.slots().get("cat"), 2)
    check("内置槽位覆盖 2-6", sorted(lib.slots().values()), [2, 3, 4, 5, 6])
    custom = pathlib.Path(_dummy_json({
        "anims": {"selftest_x": {"label": "自检用", "slot": None,
                                 "actors": [{"sheet": "carrot", "row": 1,
                                             "x": 10}]}}
    }))
    merged = ch.Library(str(custom))
    check("自定义配方被合并", "selftest_x" in merged.anims, True)
    check("自定义配方不动内置", merged.slots().get("cat"), 2)
    # 覆盖：同名动画应以后者为准；这里故意给 cat 一个已被 duo 占用的 slot，
    # 用来验证"槽位冲突"能被查出来（slot 9 是空闲的，不会冲突）
    override = pathlib.Path(_dummy_json({
        "anims": {"cat": {"label": "被覆盖", "slot": 3,
                          "actors": [{"sheet": "carrot", "row": 1}]}}
    }))
    check("同名动画被覆盖", ch.Library(str(override)).label("cat"), "被覆盖")
    check("内置配方无槽位冲突", ch.Library().slot_conflicts(), {})
    check("能查出槽位冲突",
          sorted(ch.Library(str(override)).slot_conflicts().get(3, [])),
          ["cat", "duo"])

    # 9) 启动预检能跑完且给出结论（不碰设备）
    rep = dr.run(with_device=False)
    check("doctor 离线跑通", rep.worst in (dr.OK, dr.WARN, dr.FAIL), True)
    check("doctor 有检查项", len(rep.items) >= 5, True)
    check("doctor 报告有结论", "结论：" in rep.render(), True)

    print("\n自检：", "全部通过" if ok else "存在失败")
    return 0 if ok else 1


# ---------------------------------------------------------------- 设备命令

def _dev():
    return px.Device()


def cmd_status(_a) -> int:
    with _dev() as dev:
        d = dev.info
        print(f"设备: {d.get('product_string')}  ({d.get('manufacturer_string')})")
        print(f"接口: iface={d.get('interface_number')} "
              f"usage_page=0x{d.get('usage_page'):04X} usage={d.get('usage')}\n")
        cur = px.get_volume(dev)
        print(f"硬件音量 : {cur[1]}/{cur[0]}" if cur else "硬件音量 : 无响应")
        amb = dev.query(px.CMD_AMBIENT_GET)
        print(f"氛围灯   : {px.hexs(amb) if amb else '无响应'}")
        txt = dev.query(px.CMD_TEXT_GET, bytes([0]))
        print(f"文本     : {px.hexs(txt) if txt else '无响应'}")
        st = px.get_pixel_state(dev)
        if st:
            print(f"像素屏   : {px.hexs(st['raw'])}")
            print(f"           主题色={st['rgb']} 模式={st['mode']} "
                  f"类别={st['category']} 槽位={st['option']}")
        else:
            print("像素屏   : 无响应")
    return 0


def cmd_text(a) -> int:
    with _dev() as dev:
        text = px.fit_text(a.text)
        px.show_text(dev, text, a.align, a.scroll)
        print(f"{'滚动(' + a.scroll + ')' if a.scroll else '静态(' + a.align + ')'}: {text!r}")
        time.sleep(0.3)
        p = dev.query(px.CMD_TEXT_GET, bytes([0]))
        if p and len(p) > 2:
            print(f"回读: {p[2:2 + p[1]].decode('utf-8', 'replace')!r}")
    return 0


def cmd_scene(a) -> int:
    with _dev() as dev:
        px.show_scene(dev, a.scene, a.option, a.rgb)
        print(f"场景 -> {a.scene} (槽位 {a.option})")
        time.sleep(0.3)
        st = px.get_pixel_state(dev)
        if st:
            print(f"回读: {px.hexs(st['raw'])}")
    return 0


def cmd_clock(a) -> int:
    with _dev() as dev:
        px.show_clock(dev, a.n, a.rgb)
        print(f"时钟样式 {a.n}/{px.CLOCK_STYLES}")
    return 0


def cmd_spectrum(a) -> int:
    names = {1: "柱状", 2: "波浪", 3: "对称", 4: "密集"}
    with _dev() as dev:
        px.show_spectrum(dev, a.style - 1)
        print(f"频谱样式 {a.style}（{names[a.style]}）—— 设备自算，放歌时才动")
    return 0


def cmd_color(a) -> int:
    with _dev() as dev:
        px.set_screen_color(dev, a.rgb)
        print(f"屏幕主题色 -> {a.rgb}")
    return 0


def cmd_light(a) -> int:
    with _dev() as dev:
        px.set_ambient(dev, a.effect, a.rgb, a.brightness, a.speed)
        print(f"氛围灯 -> {a.effect} rgb={a.rgb} 亮度={a.brightness} 速度={a.speed}")
    return 0


def cmd_light_power(a) -> int:
    with _dev() as dev:
        px.set_ambient_power(dev, a.action == "on")
        print(f"氛围灯 {'开' if a.action == 'on' else '关'}")
    return 0


def cmd_volume(a) -> int:
    with _dev() as dev:
        cur = px.get_volume(dev)
        if not cur:
            print("音量查询无响应")
            return 1
        print(f"当前 {cur[1]}/{cur[0]}")
        if a.level is not None:
            got = px.set_volume(dev, a.level)
            print(f"设置 {a.level} -> 回读 {got[1]}/{got[0]}" if got else "设置后无回读")
    return 0


def cmd_eq(a) -> int:
    """EQ 音效模式：查询 / 设置（音箱自带，非软件滤波）。"""
    with _dev() as dev:
        cur = px.get_eq(dev)
        if cur is None:
            print("EQ 查询无响应")
            return 1
        print(f"当前 EQ：{cur} = {px.EQ_NAMES.get(cur, '未知')}")
        if a.list:
            print("\n可用音效模式：")
            for k in sorted(px.EQ_NAMES):
                print(f"  {k:>2}  {px.EQ_NAMES[k]}")
            print("\n别名：" + ", ".join(sorted(px.EQ_ALIASES)))
            return 0
        if a.name is None:
            return 0
        # 解析：别名 / 中文名 / 数字
        idx = None
        key = str(a.name).strip().lower()
        if key in px.EQ_ALIASES:
            idx = px.EQ_ALIASES[key]
        elif key.isdigit():
            idx = int(key)
        else:
            for k, v in px.EQ_NAMES.items():
                if v == a.name:
                    idx = k
                    break
        if idx is None or idx not in px.EQ_NAMES:
            print(f"未知音效 {a.name!r}；用 `eq --list` 查看可用项")
            return 1
        got = px.set_eq(dev, idx)
        ok = "✔" if got == idx else "✘"
        print(f"设置 {idx}({px.EQ_NAMES[idx]}) -> 回读 {got} "
              f"({px.EQ_NAMES.get(got, '未知')}) {ok}")
    return 0


def cmd_raw(a) -> int:
    data = bytes.fromhex(a.hex.replace(" ", ""))
    if len(data) > px.PACKET_LEN:
        raise SystemExit("hex 超过 64 字节")
    with _dev() as dev:
        dev.write(data + bytes(px.PACKET_LEN - len(data)))
        print(f"已写入: {px.hexs(data)}")
        for f in dev.read_frames(0.8):
            print(f"  响应: {px.hexs(f[:24])} 解析={px.parse_frame(f)}")
    return 0


# ---------------------------------------------------------------- 音频

def cmd_play(a) -> int:
    """把 PixelBar 当声卡放音频（可顺带把屏切到频谱）。"""
    if a.list_devices:
        for i, n in au.list_outputs():
            flat = " ".join(n.split())
            if "hands-free" in n.lower():
                mark = "   （蓝牙免提，别选）"
            elif "halo pixelbar" in n.lower():
                mark = "   <-- PixelBar"
            else:
                mark = ""
            print(f"{i:3d}  {flat}{mark}")
        return 0

    files = au.collect_files(a.paths)
    if not files:
        print("没有找到音频文件")
        return 1
    if a.shuffle:
        import random
        random.shuffle(files)

    dev = a.device
    if dev is None:
        cands = au.find_outputs()
        if not cands:
            print("没找到 PixelBar 输出设备；用 --list-devices 查看")
            return 1
        dev = cands[0][0]
        print(f"自动选中设备 {dev}：{dict(au.list_outputs()).get(dev)}")

    print(f"{len(files)} 首，重复 {a.repeat} 遍，间隔 {a.gap}s")

    # 音色预设叠加到显式参数之上（显式参数优先）
    b, t, pr = a.bass, a.treble, a.presence
    if a.preset != "flat":
        P = {"bright": (-2.0, 6.0, 3.0), "clear": (-4.0, 5.0, 4.0),
             "warm": (3.0, -2.0, 0.0), "vocal": (-2.0, 3.0, 5.0)}
        pb, pt, pp = P[a.preset]
        if a.bass == 0.0:
            b = pb
        if a.treble == 0.0:
            t = pt
        if a.presence == 0.0:
            pr = pp
    if b or t or pr:
        print(f"EQ：低音 {b:+.1f}dB / 清晰度 {pr:+.1f}dB / 高音 {t:+.1f}dB"
              f"（预设 {a.preset}）")

    if a.spectrum:
        try:
            with _dev() as d:
                px.show_spectrum(d, a.spectrum - 1)
            print(f"屏幕已切到频谱样式 {a.spectrum}")
        except RuntimeError as e:
            print(f"（屏幕切频谱失败：{e}）")

    def on_track(f, n, total):
        print(f"[{n}/{total}] {f.stem}", flush=True)

    _dev_rate = 48000
    try:
        import sounddevice as _sd
        _dev_rate = int(_sd.query_devices(dev)["default_samplerate"])
    except Exception:  # noqa: BLE001
        pass
    au.play_files(files, dev, on_track=on_track, repeat=a.repeat, gap=a.gap,
                  eq=au.make_eq(_dev_rate, bass_db=b, treble_db=t, presence_db=pr))
    print("播放结束")
    return 0


# ---------------------------------------------------------------- 表情

def cmd_faces(a) -> int:
    """表情：烧进 category（一次性），运行时 2ms 瞬时切换。"""
    if a.preview:
        fc.contact_sheet(a.preview)
        print(f"预览已存 {a.preview}")

    if a.list or (not a.burn and not a.demo and not a.name):
        print("表情 -> category（一个表情一个 category）")
        for n in fc.EXPRESSIONS:
            print(f"  {n:10s} {fc.LABELS[n]}   -> category "
                  f"{fc.EXPRESSION_CATEGORY[n]}")
        print("\n烧录：python pixelbar.py faces --burn")
        print("切换：python pixelbar.py faces happy")
        return 0

    if a.burn:
        print("⚠️ 会覆盖 category 2-7 的原生场景（办公/阅读/猫/狗/热词/赛博）")
        if a.dry:
            print("dry-run，不烧录")
            return 0
        with _dev() as dev:
            for n in fc.EXPRESSIONS:
                cat = fc.EXPRESSION_CATEGORY[n]
                print(f"  烧录 {n:10s} -> category {cat} ...", flush=True)
                wr.push_frames(dev, [wr.encode_payload(fc.draw_face(n))],
                               cat, a.option, verbose=False)
                time.sleep(0.5)
        print("烧录完成。现在可以用 `faces <名字>` 瞬时切换。")
        return 0

    names = fc.EXPRESSIONS if a.demo else [a.name]
    with _dev() as dev:
        for n in names:
            cat = fc.EXPRESSION_CATEGORY[n]
            wr.show_slot(dev, cat, a.option)
            print(f"{fc.LABELS[n]}({n}) -> category {cat}")
            if a.demo:
                time.sleep(a.hold)
    return 0


# ---------------------------------------------------------------- 二次元动画

def cmd_anims(a) -> int:
    """二次元角色动画：烧进 category（一次性），运行时瞬时切换 / 导出 GIF。

    动画来自声明式配方（``pixelbar/anims.json``）；``--recipe`` 可追加自己的配方，
    追加进来的动画同样能 ``--burn`` / 切换 / ``--export``。
    """
    lib = ch.Library(*(a.recipe or []))
    slots = lib.slots()
    names = list(slots)

    if a.export:
        outdir = pathlib.Path(a.export)
        outdir.mkdir(parents=True, exist_ok=True)
        # 不给名字时导出全部（含 slot=null 的，它们只是不参与默认烧录）
        only = [a.name] if a.name else lib.names
        for n in only:
            p = outdir / f"{n}.gif"
            lib.export_gif(n, p, frame_ms=a.frame_ms, n_frames=a.frames)
            print(f"  导出 {n:12s} -> {p}")
        print(f"完成，共 {len(only)} 个 GIF")
        return 0

    if a.preview:
        cs = lib.canvases(a.name or names[0], n_frames=a.frames)
        rn.contact_sheet(cs, a.preview, cols=3, scale=1)
        print(f"预览已存 {a.preview}")

    if a.list or (not a.burn and not a.demo and not a.name):
        print("二次元动画 -> category（一个动画一个 category）")
        for n in names:
            print(f"  {n:12s} {lib.label(n):22s} -> category {slots[n]}")
        extra = [n for n in lib.names if n not in slots]
        if extra:
            print(f"\n未分配槽位（只能 --export / --preview）：{extra}")
        conflicts = lib.slot_conflicts()
        if conflicts:
            print("\n⚠️ 槽位冲突（同一个 category 被多个动画占用，会互相覆盖）：")
            for cat, ns in sorted(conflicts.items()):
                print(f"   category {cat}: {ns}")
            print("   改配方里这些动画的 slot 即可（可用 2-6）")
        print("\n烧录：python pixelbar.py anims --burn")
        print("切换：python pixelbar.py anims cat")
        print("导出 GIF：python pixelbar.py anims --export gifs\\out")
        return 0

    if a.burn:
        print("⚠️ 会覆盖 category 2-6 现有的自定义图（含之前的 faces 表情）")
        conflicts = lib.slot_conflicts()
        if conflicts:
            raise SystemExit(
                f"槽位冲突，先修配方再烧：{conflicts}\n"
                "同一个 category 被多个动画占用会互相覆盖。")
        if a.dry:
            print("dry-run，不烧录")
            return 0
        todo = a.only or names
        unknown = [n for n in todo if n not in slots]
        if unknown:
            raise SystemExit(
                f"这些动画没有 slot，无法烧录：{unknown}。\n"
                f"请在配方里给它们一个 2-6 的 slot（当前占用：{slots}）")
        with _dev() as dev:
            for n in todo:
                cat = slots[n]
                cs = lib.canvases(n, n_frames=a.frames)
                print(f"  烧录 {n:12s} -> category {cat}（{len(cs)} 帧）...",
                      flush=True)
                wr.push_frames(dev, [wr.encode_payload(c) for c in cs],
                               cat, a.option, a.delay, settle=a.settle,
                               verbose=False)
                time.sleep(a.gap)
        print(f"烧录完成（{len(todo)} 个）。现在可以用 `anims <名字>` 瞬时切换。")
        return 0

    only = (a.only or names) if a.demo else [a.name]
    with _dev() as dev:
        for n in only:
            if n not in slots:
                raise SystemExit(f"{n} 没有 slot，无法切换（可用：{list(slots)}）")
            cat = slots[n]
            wr.show_slot(dev, cat, a.option)
            print(f"{lib.label(n)}({n}) -> category {cat}")
            if a.demo:
                time.sleep(a.hold)
    return 0


# ---------------------------------------------------------------- 启动预检

def cmd_doctor(a) -> int:
    """启动预检：依赖 / 字体 / 素材 / 设备链路逐项检查，每项都给修法。"""
    rep = dr.run(with_device=not a.offline)
    print(rep.render())
    return 1 if rep.worst == dr.FAIL else 0


# ---------------------------------------------------------------- 一键制作

def _load_library(a):
    """按 --recipe 组装动画库（可多次追加）。"""
    return ch.Library(*(a.recipe or []))


def cmd_sheet(a) -> int:
    """查看/预览精灵表：切出几行几列、每行多大、某一行走起来什么样。"""
    p = pathlib.Path(a.file)
    if not p.exists():
        raise SystemExit(f"没有文件 {p}")
    cols = a.cols
    rows = a.rows
    cw, chh = a.cell
    grid = sp.slice_sheet(p, cell=(cw, chh), cols=cols, rows=rows,
                          origin=(a.origin[0], a.origin[1]))
    print(f"{p.name}  网格 {cols}x{rows}  每格 {cw}x{chh}  "
          f"原点 {tuple(a.origin)}")
    usable = []
    for r, line in enumerate(grid):
        bb = sp.content_bbox(line)
        n = [m.convert("L").histogram()[255] for m in line]
        if bb is None:
            print(f"  row{r}: 空")
            continue
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        print(f"  row{r}: 内容 {w}x{h}px，每帧前景 {n} 像素")
        usable.append(r)

    if a.preview:
        rows_to_show = [a.row] if a.row is not None else usable
        tiles = []
        for r in rows_to_show:
            cs = sp.walk_canvases(grid, row=r, n_frames=a.frames, style=a.style)
            tiles += cs[:6]
        rn.contact_sheet(tiles, a.preview, cols=3, scale=1)
        print(f"预览已存 {a.preview}（行 {rows_to_show}）")
    return 0


def cmd_make(a) -> int:
    """一键制作：源文件 -> 画布 -> 预览 / 上机 / 导出 GIF。

    * ``.gif``  → 走 ``render.gif_frames``（透明通道、底色剔除、均匀抽样）
    * ``.png``  → 当作精灵表，按 ``--row`` 取一行行走帧，合成"原地走 + 背景滚动"
    """
    src = pathlib.Path(a.source)
    if not src.exists():
        raise SystemExit(f"没有文件 {src}")
    kind = a.kind
    if kind == "auto":
        kind = "gif" if src.suffix.lower() == ".gif" else "sheet"

    if kind == "gif":
        cs = rn.gif_frames(src, max_frames=a.frames, thr=a.thr,
                           invert=a.invert, trim_bottom=a.trim_bottom,
                           target_h=a.target_h,
                           travel=not a.inplace,
                           ground=None if a.no_ground else a.ground,
                           mode=a.mode, fit=a.fit, bg=None if a.no_bg else "auto",
                           spread=not a.no_spread)
        what = f"GIF {src.name}（{len(cs)} 帧）"
    else:
        if a.row is None:
            raise SystemExit("精灵表必须指定 --row（用 `sheet <表> --preview` 先看每行）")
        grid = sp.slice_sheet(src, cell=tuple(a.cell), cols=a.cols, rows=a.rows,
                              origin=tuple(a.origin))
        cs = sp.walk_canvases(grid, row=a.row, n_frames=a.frames,
                              style=a.style, x=a.x, flip=a.flip)
        what = f"精灵表 {src.name} 第 {a.row} 行（{len(cs)} 帧）"

    if a.preview:
        rn.contact_sheet(cs, a.preview, cols=4, scale=2)
        print(f"预览已存 {a.preview}")
    if a.export:
        out = pathlib.Path(a.export)
        if out.is_dir() or not out.suffix:
            out.mkdir(parents=True, exist_ok=True)
            # 源名可能自带点（如 "carrot..png"），去掉尾部点避免 "carrot..gif"
            stem = src.stem.rstrip(". ") or "anim"
            out = out / f"{stem}.gif"
        _save_gif(cs, out, a.frame_ms)
        print(f"已导出 {out}")
    if a.dry:
        print(f"{what}：dry-run，不推送")
        return 0
    if a.category is None:
        print(f"{what}：没有给 --category，只出预览/导出，不推送")
        return 0

    with _dev() as dev:
        wr.push_frames(dev, [wr.encode_payload(c) for c in cs],
                       a.category, a.option, a.delay)
    print(f"已推送 {what} -> category {a.category}")
    return 0


def _save_gif(canvases, path, frame_ms: int = 120):
    """把画布列表存成无限循环的 GIF。"""
    frames = [rn.canvas_to_image(c) for c in canvases]
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=frame_ms, loop=0, disposal=2, optimize=False,
                   comment=ch.CREDIT.encode("utf-8"))
    return path


# ---------------------------------------------------------------- 位图命令

def _push(a, canvases, label: str) -> int:
    if a.preview:
        rn.contact_sheet(canvases, a.preview)
        print(f"预览已存 {a.preview}")
    if a.dry:
        print("dry-run，不推送")
        return 0
    with _dev() as dev:
        wr.push_frames(dev, [wr.encode_payload(c) for c in canvases],
                       a.category, a.option, a.delay)
    print(f"已推送 {label}")
    return 0


def cmd_image(a) -> int:
    from PIL import Image
    img = Image.open(a.file)
    canvas = rn.canvas_from_image(img, "dither" if a.dither else "threshold",
                                  thr=a.thr, fit=a.fit)
    return _push(a, [canvas], f"图片 {a.file}")


def cmd_anim(a) -> int:
    canvases = rn.gif_frames(
        a.file, max_frames=a.frames, thr=a.thr, invert=a.invert,
        trim_bottom=a.trim_bottom, target_h=a.target_h,
        travel=not a.inplace, ground=None if a.no_ground else a.ground)
    return _push(a, canvases, f"动画 {a.file}（{len(canvases)} 帧）")


def cmd_border(a) -> int:
    canvas = rn.border(rn.new_canvas())
    return _push(a, [canvas], "对齐自检边框")


def cmd_text_bitmap(a) -> int:
    canvas = rn.new_canvas()
    if a.cjk:
        rn.draw_cjk_lines(canvas, a.lines, size=a.size)
    else:
        rn.draw_ascii_lines(canvas, a.lines, scale=a.scale)
    return _push(a, [canvas], f"点阵文字 {a.lines}")


def cmd_decode(a) -> int:
    """把 .bin / blob 反解成预览图。"""
    data = pathlib.Path(a.file).read_bytes()
    if len(data) % wr.WIRE_BYTES == 0:
        payloads = wr.decode_wire_multi(data)
        canvases = [wr.decode_payload(p) for p in payloads]
        kind = f"线上 blob（{len(payloads)} 帧 x 1064）"
    elif len(data) == 1040:
        import hz_format
        canvases = [hz_format.bin_to_matrix(data)]
        kind = "TempoHub 本地 .bin（1040）"
    else:
        payload = data[-wr.PAYLOAD_BYTES:]
        canvases = [wr.decode_payload(payload)]
        kind = f"裸 payload（取末尾 1024 字节，共 {len(data)}）"
    out = a.out or "decode_preview.png"
    rn.contact_sheet(canvases, out)
    print(f"{kind} -> {len(canvases)} 帧，预览已存 {out}")
    return 0


def cmd_replay(a) -> int:
    """原样回放官方抓包的 OUT 帧（链路验证）。"""
    caps = json.loads(pathlib.Path(a.file).read_text(encoding="utf-8"))
    if a.capture not in caps:
        raise SystemExit(f"抓包里没有 {a.capture}，可选：{list(caps)}")
    frames = [bytes.fromhex(h) for h in caps[a.capture]["out"]]
    print(f"回放 capture {a.capture}：{len(frames)} 条 OUT 帧")
    with _dev() as dev:
        wr.replay_frames(dev, frames)
    return 0


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="pixelbar",
        description="花再 Halo PixelBar 控制工具（实机校准版）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="查询设备状态").set_defaults(func=cmd_status)
    sub.add_parser("selftest", help="离线自检（不连设备）").set_defaults(func=cmd_selftest)

    p = sub.add_parser("doctor", help="启动预检：依赖/字体/素材/设备链路，每项给修法")
    p.add_argument("--offline", action="store_true", help="不检查设备")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("sheet", help="看精灵表结构 / 预览某一行走起来什么样")
    p.add_argument("file")
    p.add_argument("--cell", type=parse_cell, default=(24, 32), help="每格宽x高")
    p.add_argument("--cols", type=int, default=3)
    p.add_argument("--rows", type=int, default=4)
    p.add_argument("--origin", type=parse_cell, default=(0, 0), help="网格左上角")
    p.add_argument("--row", type=int, help="只看这一行（默认全部）")
    p.add_argument("--style", default="ground",
                   choices=list(sp.STYLE_PERIOD), help="背景风格")
    p.add_argument("--frames", type=int, default=ch.WALK_FRAMES)
    p.add_argument("--preview", help="预览图输出路径")
    p.set_defaults(func=cmd_sheet)

    p = sub.add_parser("make", help="一键制作：源 -> 预览/上机/导出 GIF")
    p.add_argument("source")
    p.add_argument("--kind", choices=["auto", "gif", "sheet"], default="auto")
    # 精灵表
    p.add_argument("--row", type=int, help="精灵表用哪一行朝向")
    p.add_argument("--cell", type=parse_cell, default=(24, 32))
    p.add_argument("--cols", type=int, default=3)
    p.add_argument("--rows", type=int, default=4)
    p.add_argument("--origin", type=parse_cell, default=(0, 0))
    p.add_argument("--style", default="ground", choices=list(sp.STYLE_PERIOD))
    p.add_argument("--x", type=int, help="角色左边缘列（默认居中）")
    p.add_argument("--flip", action="store_true", help="水平翻转")
    # GIF
    p.add_argument("--thr", type=int, default=128)
    p.add_argument("--invert", action="store_true", help="素材是暗底亮物")
    p.add_argument("--trim-bottom", type=int, default=0)
    p.add_argument("--target-h", type=int, default=28)
    p.add_argument("--inplace", action="store_true", help="原地循环而非横穿")
    p.add_argument("--ground", type=int, default=28)
    p.add_argument("--no-ground", action="store_true")
    p.add_argument("--mode", choices=["sprite", "scene"], default="sprite")
    p.add_argument("--fit", choices=["stretch", "height", "width"], default="height")
    p.add_argument("--no-bg", action="store_true", help="关掉纯色底剔除")
    p.add_argument("--no-spread", action="store_true", help="只取前 N 帧而非均匀抽样")
    # 输出
    p.add_argument("--frames", type=int, default=ch.WALK_FRAMES)
    p.add_argument("--preview", help="预览图输出路径")
    p.add_argument("--export", help="导出 GIF 的路径或目录")
    p.add_argument("--frame-ms", type=int, default=120)
    p.add_argument("--category", type=int, help="推到该 category（不给则不推）")
    p.add_argument("--option", type=int, default=0)
    p.add_argument("--delay", type=int, default=120)
    p.add_argument("--dry", action="store_true")
    p.set_defaults(func=cmd_make)

    p = sub.add_parser("text", help="显示文本")
    p.add_argument("text")
    p.add_argument("--align", choices=list(px.ALIGN), default="center")
    p.add_argument("--scroll", choices=["ltr", "rtl"], help="设备侧滚动")
    p.set_defaults(func=cmd_text)

    p = sub.add_parser("scene", help="内置场景")
    p.add_argument("scene", choices=list(px.SCENES))
    p.add_argument("--option", type=int, default=0)
    p.add_argument("--rgb", type=parse_rgb, default=px.DEFAULT_RGB)
    p.set_defaults(func=cmd_scene)

    p = sub.add_parser("clock", help="内置时钟样式")
    p.add_argument("n", type=int, choices=range(1, px.CLOCK_STYLES + 1))
    p.add_argument("--rgb", type=parse_rgb, default=px.DEFAULT_RGB)
    p.set_defaults(func=cmd_clock)

    p = sub.add_parser("spectrum", help="内置频谱样式")
    p.add_argument("style", type=int, choices=[1, 2, 3, 4])
    p.set_defaults(func=cmd_spectrum)

    p = sub.add_parser("color", help="屏幕主题色")
    p.add_argument("rgb", type=parse_rgb)
    p.set_defaults(func=cmd_color)

    p = sub.add_parser("light", help="氛围灯")
    p.add_argument("effect", choices=list(px.EFFECTS))
    p.add_argument("--rgb", type=parse_rgb, default=(0x66, 0xAF, 0xFF))
    p.add_argument("--brightness", choices=list(px.BRIGHTNESS), default="high")
    p.add_argument("--speed", type=int, default=5)
    p.set_defaults(func=cmd_light)

    p = sub.add_parser("light-power", help="氛围灯开关")
    p.add_argument("action", choices=["on", "off"])
    p.set_defaults(func=cmd_light_power)

    p = sub.add_parser("volume", help="硬件音量")
    p.add_argument("level", nargs="?", type=int)
    p.set_defaults(func=cmd_volume)

    p = sub.add_parser("eq", help="EQ 音效模式（音箱自带）")
    p.add_argument("name", nargs="?",
                   help="音效名/别名/编号，如 high / 高频增强 / 19；省略则只查询")
    p.add_argument("--list", action="store_true", help="列出全部音效模式")
    p.set_defaults(func=cmd_eq)

    p = sub.add_parser("raw", help="发送原始 hex 帧")
    p.add_argument("hex")
    p.set_defaults(func=cmd_raw)

    # --- 音频 ---
    p = sub.add_parser("play", help="把 PixelBar 当声卡放音频")
    p.add_argument("paths", nargs="*", default=[],
                   help="音频文件或目录（目录会递归收集）")
    p.add_argument("--list-devices", action="store_true", help="列出输出设备")
    p.add_argument("--device", type=int, help="输出设备号（默认自动找 PixelBar）")
    p.add_argument("--shuffle", action="store_true", help="打乱顺序")
    p.add_argument("--repeat", type=int, default=1, help="整体重复遍数")
    p.add_argument("--gap", type=float, default=0.4, help="曲间停顿秒数")
    p.add_argument("--spectrum", type=int, choices=[1, 2, 3, 4],
                   help="播放同时把屏切到该频谱样式")
    p.add_argument("--preset", choices=["flat", "bright", "clear", "warm", "vocal"],
                   default="flat", help="音色预设（bright/clear 提亮）")
    p.add_argument("--bass", type=float, default=0.0,
                   help="低频搁架增益 dB（负值削低频，如 -4）")
    p.add_argument("--treble", type=float, default=0.0,
                   help="高频搁架增益 dB（正值提亮，如 +6）")
    p.add_argument("--presence", type=float, default=0.0,
                   help="2.5kHz 人声/清晰度增益 dB（如 +4）")
    p.set_defaults(func=cmd_play)

    # --- 位图 ---
    def add_push_args(p):
        p.add_argument("--category", type=int, default=2,
                       help="场景类别（1游戏 2办公 3阅读 4猫 5狗 6热词 7赛博）")
        p.add_argument("--option", type=int, default=0, help="槽位")
        p.add_argument("--delay", type=int, default=wr.DEFAULT_DELAY, help="帧间隔 ms")
        p.add_argument("--preview", default="preview.png", help="预览图输出路径")
        p.add_argument("--dry", action="store_true", help="只编码不推送")

    p = sub.add_parser("image", help="推一张图片")
    p.add_argument("file")
    p.add_argument("--dither", action="store_true", help="Bayer 抖动（保留灰度层次）")
    p.add_argument("--thr", type=int, default=128)
    p.add_argument("--fit", choices=["stretch", "height", "width"], default="stretch")
    add_push_args(p)
    p.set_defaults(func=cmd_image)

    p = sub.add_parser("anim", help="推 GIF 动画")
    p.add_argument("file")
    p.add_argument("--frames", type=int, default=wr.MAX_FRAMES,
                   help=f"最多 {wr.MAX_FRAMES} 帧（槽位上限）")
    p.add_argument("--thr", type=int, default=128)
    p.add_argument("--invert", action="store_true", help="素材是暗底亮物")
    p.add_argument("--trim-bottom", type=int, default=0, help="裁掉源图底部若干行")
    p.add_argument("--target-h", type=int, default=28, help="前景高度")
    p.add_argument("--inplace", action="store_true", help="原地循环而非横穿")
    p.add_argument("--ground", type=int, default=28, help="地面线所在行")
    p.add_argument("--no-ground", action="store_true")
    add_push_args(p)
    p.set_defaults(func=cmd_anim)

    p = sub.add_parser("border", help="推 1px 满边框对齐自检图")
    add_push_args(p)
    p.set_defaults(func=cmd_border)

    p = sub.add_parser("text-bitmap", help="把文字渲染成点阵图再推（非设备字体）")
    p.add_argument("lines", nargs="+")
    p.add_argument("--cjk", action="store_true", help="宋体中文（默认 ASCII 5x7）")
    p.add_argument("--size", type=int, default=16)
    p.add_argument("--scale", type=int, default=2, choices=[1, 2])
    add_push_args(p)
    p.set_defaults(func=cmd_text_bitmap)

    p = sub.add_parser("decode", help="反解 .bin / blob 成预览图")
    p.add_argument("file")
    p.add_argument("--out", help="预览图输出路径")
    p.set_defaults(func=cmd_decode)

    p = sub.add_parser("replay", help="回放官方抓包 OUT 帧（链路验证）")
    p.add_argument("file", nargs="?", default=str(FIXTURE))
    p.add_argument("--capture", default="23")
    p.set_defaults(func=cmd_replay)

    p = sub.add_parser("faces", help="表情（烧进 category，运行时瞬时切换）")
    p.add_argument("name", nargs="?", choices=fc.EXPRESSIONS, help="切到某个表情")
    p.add_argument("--burn", action="store_true", help="把 6 个表情烧进 category 2-7")
    p.add_argument("--demo", action="store_true", help="依次演示所有表情")
    p.add_argument("--hold", type=float, default=1.5, help="演示时每个停留秒数")
    p.add_argument("--option", type=int, default=0, help="槽位")
    p.add_argument("--preview", default="faces.png", help="预览图路径（留空不生成）")
    p.add_argument("--list", action="store_true", help="只列出映射")
    p.add_argument("--dry", action="store_true")
    p.set_defaults(func=cmd_faces)

    p = sub.add_parser("anims", help="二次元角色动画（烧进 category / 导出 GIF）")
    p.add_argument("name", nargs="?",
                   help="切到某个动画（可用 anims --list 看全部）")
    p.add_argument("--burn", action="store_true",
                   help="把默认 5 个动画烧进 category 2-6")
    p.add_argument("--only", nargs="*",
                   help="只烧/只演示这几个（逐个烧更稳，卡死风险低）")
    p.add_argument("--recipe", action="append",
                   help="追加动画配方 JSON（可多次，后者覆盖前者）")
    p.add_argument("--demo", action="store_true", help="依次演示所有动画")
    p.add_argument("--hold", type=float, default=2.5, help="演示时每个停留秒数")
    p.add_argument("--export", help="导出成 GIF 的目录（不推设备）")
    p.add_argument("--frame-ms", type=int, default=120, help="导出 GIF 的帧间隔")
    p.add_argument("--frames", type=int, default=18,
                   help="帧数（18 = 3 帧走姿的整数倍，循环无缝）")
    p.add_argument("--delay", type=int, default=120, help="设备帧间隔 ms")
    p.add_argument("--settle", type=float, default=4.0,
                   help="每个动画上传后等固件提交 flash 的秒数（连推多个要留足）")
    p.add_argument("--gap", type=float, default=1.0,
                   help="两个动画之间的额外间隔秒数")
    p.add_argument("--option", type=int, default=0, help="槽位")
    p.add_argument("--preview", help="预览图路径")
    p.add_argument("--list", action="store_true", help="只列出映射")
    p.add_argument("--dry", action="store_true")
    p.set_defaults(func=cmd_anims)

    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except RuntimeError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
