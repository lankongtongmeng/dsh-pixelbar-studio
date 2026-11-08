#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""花再 Halo PixelBar 控制工具包。

分层结构::

    protocol  设备发现 / 帧构造解析 / 命令封装（文本、场景、灯效、音量）
    wire      0x17 位图上传的线上格式（1064 = 8x133）与上传时序
    render    绘制层（ASCII 点阵 / 宋体中文 / 图片 / GIF -> 256x32 画布）
    sprite    精灵表切片 + 行走场景合成（视差背景、无缝循环）
    chars     二次元角色动画库（声明式配方 anims.json 驱动）
    faces     表情库（烧进 category，运行时瞬时切换）
    audio     把 PixelBar 当声卡播放
    doctor    启动预检（依赖 / 字体 / 素材 / 设备链路）

典型用法::

    from pixelbar import protocol as px, wire as wr, render as rn, chars as ch

    with px.Device() as dev:
        px.show_text(dev, "你好")                     # 设备字体文本
        px.show_scene(dev, "cats")                    # 内置场景

        canvas = rn.new_canvas()
        rn.draw_cjk_lines(canvas, ["花再像素屏"])
        wr.push_frames(dev, [wr.encode_payload(canvas)], category=2)

        frames = rn.gif_frames("cat.gif", max_frames=20)   # GIF 动画
        wr.push_frames(dev, [wr.encode_payload(c) for c in frames], category=2)

        cs = ch.canvases("duo")                            # 二次元角色动画
        wr.push_frames(dev, [wr.encode_payload(c) for c in cs], category=3)

命令行见 ``python pixelbar.py --help``；**开工先跑** ``doctor`` 与 ``selftest``。
制作流程见 docs/WORKFLOW.md，协议细节见 docs/PROTOCOL.md。

素材署名：``gifs/oga/`` 的角色美术来自 David Revoy 的 Pepper&Carrot，
授权 **CC-BY 4.0 / 3.0，二次分发须署名**（见 ``chars.CREDIT``）。
"""
from . import (audio, chars, doctor, faces, protocol, render, sprite,  # noqa: F401
               wire)

__all__ = ["protocol", "wire", "render", "sprite", "chars", "faces",
           "audio", "doctor"]
__version__ = "1.1.0"
