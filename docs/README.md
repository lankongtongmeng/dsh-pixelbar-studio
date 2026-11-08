# 花再 Halo PixelBar 控制工具

针对 **VID 0x2D99 / PID 0xA106** 的实机校准版控制工具，覆盖点阵屏文本、内置场景/时钟/频谱、
自定义位图与 GIF 动画、二次元角色动画、氛围灯、硬件音量。

- **开工先看** → [WORKFLOW.md](WORKFLOW.md)：从零到「动画在设备上跑起来」的可照做流程
- 协议细节 → [PROTOCOL.md](PROTOCOL.md)
- 参考来源与有效性评估 → [REFERENCES.md](REFERENCES.md)

---

## 安装

```bash
python -m pip install --user hidapi pillow
```

> ⚠️ 依赖是 **`hidapi`**，不是 PyPI 上同名的 `hid` 包。

硬件要求：用 **USB-C 数据线**连接（纯充电线不行）。蓝牙模式只走音频，控制接口不枚举。

---

## 快速开始

Windows 上有现成启动器，会顺手切好 UTF-8（否则中文输出乱码）并补依赖：

```bat
run.cmd                :: 启动预检（等于 doctor）
run.cmd selftest       :: 离线自检
run.cmd anims cat      :: 切换动画
run.cmd --help         :: 全部命令
```

直接跑 Python 也一样：

```bash
# 1) 启动预检：依赖 / 字体 / 素材 / 设备链路，每项都会给修法
python pixelbar.py doctor

# 2) 离线自检（不连设备，验证环境与编解码正确）
python pixelbar.py selftest

# 3) 看设备
python pixelbar.py status

# 4) 让它说句话
python pixelbar.py text "你好，花再"
```

> 这三步是**每次开工的固定动作**：`doctor` 挡环境问题，`selftest` 挡代码问题，
> `status` 确认线插对了。跳过它们，后面遇到的现象会被误判成协议问题。

---

## 命令一览

### 屏幕内容

| 命令 | 说明 |
|---|---|
| `text "内容"` | 设备字体文本（`--align` 对齐，`--scroll ltr\|rtl` 滚动） |
| `scene <名>` | 内置场景：`clock game work read cats dogs memes cyber waves` |
| `clock <1-11>` | 内置时钟样式 |
| `spectrum <1-4>` | 内置频谱（设备自算，**放歌时才动**） |
| `color RRGGBB` | 屏幕主题色（单色屏的整屏色调） |
| `image <图片>` | 推一张图片（`--dither` 保留灰度层次） |
| `anim <GIF>` | 推 GIF 动画（设备自播） |
| `anims` | **二次元角色动画**：内置 11 个行走动画，可烧进 category / 导出 GIF |
| `sheet <表.png>` | 看精灵表结构：切出几行几列、每行多大、某一行走起来什么样 |
| `make <源>` | **一键制作**：源（GIF / 精灵表）→ 预览 / 上机 / 导出 GIF |
| `faces` | **表情**：烧进 category，运行时约 2ms 瞬时切换 |
| `border` | 推 1px 满边框，肉眼检查对齐 |
| `text-bitmap "文字"` | 把文字渲染成点阵图再推（`--cjk` 用宋体中文） |

### 音频（音箱本来就是声卡）

| 命令 | 说明 |
|---|---|
| `play <文件或目录>` | 播放音频（目录递归；支持 `.txt` 播放列表） |
| `play --list-devices` | 列出输出设备（标出 PixelBar，并排除蓝牙免提） |
| `play <dir> --spectrum 1` | **播放同时把屏切到频谱**，跟着音乐跳 |

### 设备设置

| 命令 | 说明 |
|---|---|
| `light <效果>` | 氛围灯：`breathing color_tide static ripple flow dynamic` |
| `light-power on\|off` | 氛围灯总开关 |
| `volume [等级]` | 查询/设置硬件音量 |

### 诊断

| 命令 | 说明 |
|---|---|
| `doctor` | **启动预检**：依赖 / 字体 / 素材 / 设备链路，每项都给修法（`--offline` 跳过设备） |
| `selftest` | 离线自检（52 项，含官方抓包逐字节复现） |
| `status` | 查询设备状态 |
| `decode <文件>` | 把 .bin / blob 反解成预览图 |
| `replay --capture 23` | 原样回放官方抓包，验证链路 |
| `raw <hex>` | 发送原始 hex 帧（调试用） |

---

## 常用工作流

> **完整制作流程见 [WORKFLOW.md](WORKFLOW.md)** —— 那份是"照做就行"的 SOP
> （启动 → 选素材 → 制作 → 上机 → 验证），含每一步"做完怎么知道对了"。
> 下面只是速查。

### 一键制作（推荐入口）

```bash
python pixelbar.py sheet "gifs/oga/carrot..png" --preview check.png
python pixelbar.py make  "gifs/oga/carrot..png" --row 1 \
    --preview cat.png --export gifs/anime/ --category 2
```

`make` 会自动判源类型：`.gif` 走 GIF 管线，`.png` 当精灵表（需 `--row`）。
不给 `--category` 就只出预览/导出，不碰设备。

### 推自定义位图

```bash
python pixelbar.py image photo.png --category 4 --preview out.png
```

* `--category`：写入哪个场景槽位（1游戏 2办公 3阅读 4猫 5狗 6热词 7赛博）
* `--dither`：照片等连续色调用抖动更耐看
* `--dry`：只编码不推送，先看 `--preview` 出来的预览图

### 推 GIF 动画

```bash
python pixelbar.py anim cat.gif --category 4 --frames 20
```

设备**自己循环播放**，不占电脑资源。常用参数：

| 参数 | 用途 |
|---|---|
| `--frames N` | 最多 20 帧（槽位容量上限） |
| `--invert` | 素材是"暗底亮物"时加 |
| `--trim-bottom N` | 裁掉源图底部若干行（图版边框、说明文字） |
| `--thr 0-255` | 二值化阈值，前景抓不全就调 |
| `--target-h N` | 前景高度（默认 28） |
| `--inplace` | 原地循环而非横穿屏幕 |
| `--no-ground` | 不画地面线 |
| `--mode scene` | 整帧铺满屏幕（配合 `--fit stretch\|height\|width`），适合本身就是宽幅的动画 |
| `--bg auto\|none` | 纯色底剔除（默认 auto）；透明 GIF 自动走 alpha 通道 |
| `--spread` / `--no-spread` | 长循环**均匀抽样**覆盖整个循环（默认），而不是只取前 20 帧 |

**先看预览再推**：加 `--preview out.png`，会输出多帧拼图。

> 网页 GIF 的三大坑（本工具已自动处理）：
> ① 透明背景 GIF 的透明像素在 RGB 里常是黑/白，按亮度阈值抠会把**整块背景当前景**，
> 出来是一整片实心方块 —— 必须先看 alpha 通道；
> ② 不透明但纯色底的素材同样会被整块吃掉 —— 需按底色剔除；
> ③ 只取前 N 帧会把循环动画截断成"只播前三分之一" —— 需均匀抽样。

---

### 二次元角色动画（`anims`，最推荐）

内置 10 个动漫风格行走动画，素材是 **Pepper&Carrot 24×32 角色表**
（原生像素画，和 32 像素高的屏**等高、无需缩放**，所以不糊）：

```bash
python pixelbar.py anims --list                 # 看全部动画与 category 映射
python pixelbar.py anims --burn                 # 把默认 5 个烧进 category 2-6
python pixelbar.py anims cat                    # 之后切换只要 ~2ms
python pixelbar.py anims --demo                 # 依次演示
python pixelbar.py anims --export gifs\anime    # 导出成 256x32 的 GIF 文件
```

默认烧录的 5 个（每个占一个 category）：

| 名字 | 内容 | category |
|---|---|---|
| `cat` | 小猫 Carrot 散步 | 2 |
| `duo` | Pepper 带着猫 | 3 |
| `parade` | 四人小队 | 4 |
| `town` | 小镇天际线 | 5 |
| `night` | 夜景散步（星星） | 6 |

还有 `pepper` `saffron` `coriander` `shichimi` `sakura` `hills` 可选，
用 `--only <名字>` 单独烧录（**逐个烧更稳**，见下方排障的固件卡死条目）。

**动画是声明式的**：全部定义在 `pixelbar/anims.json`，改它就能增删动画，不用碰 Python。
`slot` 给 2-6 = 参与默认烧录，给 `null` = 只在库里；`actors` 写多个就是同屏多角色
（`duo` 就是 Pepper + 猫）。也可以另存一份 JSON 用 `--recipe 我的.json` 追加覆盖。
详见 [WORKFLOW.md](WORKFLOW.md) §3.4。

> **署名要求**：素材作者 **David Revoy**，授权 **CC-BY 4.0 / CC-BY 3.0**
> （<https://opengameart.org/content/24x32-peppercarrot-characters>）。
> `--export` 导出的 GIF 会把署名写进 comment 段；二次分发请保留署名。

> 关于"网上找的二次元 GIF"：本项目实测采集了 GifCities（Internet Archive 的
> GeoCities 归档）**1380 张**动漫向 GIF 与 **497 张** 468×60 横幅，
> 结论是**大部分不适合**——它们以网页按钮、文字横幅、Web Ring 为主，
> 少数角色图缩到 28px 后也只剩难以辨认的剪影。
> 详见 [REFERENCES.md](REFERENCES.md) §8。

---

### 让音箱做表情

```bash
python pixelbar.py faces --list          # 看映射
python pixelbar.py faces --burn          # 一次性烧进 category 2-7（约 30 秒）
python pixelbar.py faces happy           # 之后切换只要 ~2ms
python pixelbar.py faces --demo          # 依次演示 6 个表情
```

6 个表情：`normal`(平静) `happy`(开心) `sad`(难过) `angry`(生气) `thinking`(思考) `celebrate`(庆祝)。

原理是**把慢的上传和快的切换分开**：表情图一次性烧进各自的 category，
运行时只发一条 0xEF 切类别，所以是瞬时响应、不擦写 flash、不占 CPU。

⚠️ 两个已知限制：

* **category 7（cyber）不可用** —— 往它推图会 ACK 成功但切过去仍显示设备原生动画。
  自定义内容请用 **category 2-6**（已逐类实测）。`celebrate` 因此需要改到其他 category。
* 占用 category 2-6 会覆盖原生场景（办公/阅读/猫/狗/热词），
  可用官方 TempoHub 重新选择原图恢复。

> 排查心法：0xEE 回读**只能确认类别/槽位，不能确认内容**。
> "协议 ACK 成功 ≠ 图写进去了" —— 遇到图不显示，先用大号数字或边框这类
> **不可认错的测试图**逐类验证，别靠猜。

### 放音乐

```bash
python pixelbar.py play --list-devices               # 找设备号
python pixelbar.py play D:\Music --spectrum 1        # 放目录 + 频谱跟着跳
python pixelbar.py play playlist.txt --shuffle       # 播放列表（每行一个路径）
```

`--device N` 可指定输出设备；不指定时自动找 PixelBar（会排除蓝牙免提那条）。

---

## 屏幕的硬约束（决定什么素材好看）

| 约束 | 含义 |
|---|---|
| **256 × 32，8:1 超宽条** | 方形素材天生吃亏（缩完只剩中间一小块）；**横向运动**的内容最合适 |
| **单色（1 bit）** | 只有亮/灭，靠抖动模拟灰度；细线小字要够粗 |
| **32 像素高** | 中文最小可读 12px、舒适 16px → **中文每屏最多 2 行**；四行只能用 ASCII 5×7 |
| **单次最多 20 帧** | 长 GIF 需抽帧 |
| **背景不能填实** | 1 位屏上"实心背景 + 实心角色"会糊成一片，角色直接消失。背景只画**轮廓线**（地面线、远山轮廓、稀疏星点） |
| **循环要真无缝** | 输出帧数取走姿帧数的整数倍；背景每帧位移取背景周期的约数，否则每循环一次"卡一下" |

适合的题材：奔跑的动物剪影、**像素角色行走（带滚动背景）**、火车、车流、海浪、烟花、星空飞船。
不适合：旋转地球这类方形素材、依赖色彩的图、细节密集的写实照片、**满屏文字横幅**。

---

## 目录结构

```
run.cmd                Windows 启动器（切 UTF-8、补依赖、无参走 doctor）
pixelbar.py            命令行入口
pyproject.toml         打包元数据（可 pip install -e . 后直接用 `pixelbar` 命令）
pixelbar/
  protocol.py          设备发现 / 帧构造解析 / 命令封装
  wire.py              0x17 线上格式（1064 = 8×133）编解码与上传时序
  render.py            绘制层（ASCII 点阵 / 宋体中文 / 图片 / GIF → 256×32）
  sprite.py            精灵表切片 + 行走场景合成（视差背景、无缝循环）
  chars.py             动画库加载器（声明式配方驱动）
  anims.json           **动画配方**：改它就能增删动画，不用改代码
  faces.py             表情库（烧进 category，瞬时切换）
  audio.py             把 PixelBar 当声卡播放
  doctor.py            启动预检
  font5x7.py           5×7 ASCII 点阵字库（生成文件）
  cli.py               命令行实现
docs/
  WORKFLOW.md          制作流程 SOP（开工先看这份）
  PROTOCOL.md          协议参考（已确认部分）
  REFERENCES.md        参考来源与有效性评估
gifs/
  oga/                 Pepper&Carrot 角色表（CC-BY，见 chars.py 署名）
  anime/               `anims --export` 导出的 GIF
  gc/ wide/            GifCities 采集池（1380 + 497 张，见 REFERENCES.md §8）
tools/                 素材采集、评分、预览、诊断脚本
tools/gen_font.py      从参考项目重新生成字库
community/             社区参考实现与官方抓包 fixtures（见 REFERENCES.md）
```

作为库使用：

```python
from pixelbar import protocol as px, wire as wr, render as rn, chars as ch

with px.Device() as dev:
    px.show_text(dev, "你好")                       # 设备字体
    px.show_scene(dev, "cats")                      # 内置场景

    canvas = rn.new_canvas()
    rn.draw_cjk_lines(canvas, ["花再像素屏"])        # 自定义位图
    wr.push_frames(dev, [wr.encode_payload(canvas)], category=2)

    frames = rn.gif_frames("cat.gif", max_frames=20)  # GIF 动画
    wr.push_frames(dev, [wr.encode_payload(c) for c in frames], category=2)

    cs = ch.canvases("duo")                          # 二次元角色动画
    wr.push_frames(dev, [wr.encode_payload(c) for c in cs], category=3)
```

---

## 排障

| 现象 | 原因 / 处理 |
|---|---|
| 找不到设备 | ① 用的是充电线而非数据线；② 走了蓝牙（HID 不枚举）；③ TempoHub 占用设备，先关掉 |
| 推完图屏不切换 | 需要 `0xEF 02` 显示帧（本工具已自动发）；也可能是 flash 未提交完，等 2 秒 |
| 屏显示「图片上传中」 | 正常现象，固件绘制，无法抑制 |
| 图整体错位 | 检查是不是发了 TempoHub 本地 .bin（1040）而非线上格式（1064）；本工具自动处理 |
| 中文显示为方块 | 设备字体不含该字形时会出现；改用 `text-bitmap --cjk` 走点阵图 |
| 文本帧发完设备掉线 | **byte4 必须为 0x00**，本工具已强制；若手工构造帧请勿填颜色索引 |
| 氛围灯设置没反应 | 需连发 3 次（本工具已处理） |
| **设备卡死、屏不动、命令全超时** | 固件卡在数据接收态：会**持续刷** `2f bb ec 17 00 04 00 03 <seq>` 且 HID 写返回 -1。**只能断电重启**（拔插 USB-C 数据线或关机重开）。本工具在上传前有链路体检，会直接报这个错而不是继续发帧 |
| 连推多个动画时中途失败 | 每个动画上传后要留足固件提交 flash 的时间，用 `--settle 4 --gap 1`（默认值），并**分批烧**（`--only a b`），别一次推 5 个 |
| `selftest` 失败 | 先看是哪一项；`复现官方抓包` 失败说明编码器被改坏了 |

---

## 免责声明

协议来自**本机互操作验证**与公开抓包分析，不保证适用于其他固件版本或其他型号
（同系列 A160 的槽位号与面板偏移与本机不同，见 PROTOCOL.md §9）。
自定义位图会写入设备 flash，请注意擦写寿命，避免高频反复上传。
