# 制作流程 SOP —— 从零到「动画在设备上跑起来」

这份文档是**可照做**的流程，不是参考手册。协议细节见 [PROTOCOL.md](PROTOCOL.md)，
命令全集见 [README.md](README.md)，素材来源评估见 [REFERENCES.md](REFERENCES.md)。

流程五步：**启动 → 选素材 → 制作 → 上机 → 验证**。每一步都有"做完怎么知道对了"。

---

## 0. 启动（每次开工先跑这三步）

```bash
python pixelbar.py doctor      # ① 预检：依赖 / 字体 / 素材 / 设备链路，逐项给修法
python pixelbar.py selftest    # ② 离线自检：52 项，含官方抓包逐字节复现编码器
python pixelbar.py status      # ③ 看设备：确认插的是数据线、能读到像素屏状态
```

`doctor` 是**唯一入口**，它会把"能不能用"拆成可逐项定位的检查：

```
[OK ] Python 版本：3.12.10
[OK ] hidapi（设备通信）：0.15.0
[OK ] 动画配方 anims.json：11 个动画、5 张角色表
[OK ] 设备链路：正常
结论：全部就绪。
```

**它报错时不要绕过去**。常见的三条：

| doctor 报什么 | 真正的原因 |
|---|---|
| `[失败] 设备：没枚举到控制接口` | ① 用了充电线而非**数据线**；② 走蓝牙（HID 不枚举）；③ TempoHub 占着设备 |
| `[失败] hidapi（设备通信）：未安装` | `python -m pip install --user hidapi`（**不是** PyPI 上的 `hid` 包） |
| `[失败] 设备链路：设备固件卡在数据接收态` | 断电重启：拔插 USB-C 数据线，或把音箱关机再开 |

> `selftest` 失败时先怀疑**测试期望值**而不是代码 —— 本项目踩过一次：
> 「校验和自洽」失败其实是期望漏加了 `0xAA`。但如果失败项是
> `复现官方抓包 capture 20/21/23`，那一定是编码器被改坏了，别放过。

---

## 1. 先想清楚：这块屏能吃什么样的素材

屏是 **256×32 单色（1 bit）、8:1 超宽条**。这三条决定了一切：

| 约束 | 直接后果 |
|---|---|
| 只有 32 像素高 | 任何素材最终都缩成 32 行；**细节在缩的过程中就死了** |
| 只有亮/灭两态 | 靠"实心剪影"表达形状；**没有灰度帮你区分主体和背景** |
| 8:1 超宽 | 方形素材缩完只占中间一小块；**横向运动**才填得满 |

### 素材优先级（这条是本项目最贵的经验）

```
原生匹配目标分辨率的像素画  >  高分辨率动漫图（缩下来）  >  低分辨率网页剪贴画
```

- **原生 24×32 的像素画**（如 Pepper&Carrot 角色表）：和屏等高，**根本不缩放**，像素不糊。
- **高分辨率图**：缩到 32px 后还能剩个大概形状。
- **90 年代网页剪贴画**（GifCities 那类）：本来就只有 30~100px，缩完是一团。实测采了
  1380 张动漫 GIF + 497 张 468×60 横幅，**结论是不适合**（见 REFERENCES.md §8）。

**不要按"名字里有没有 anime"选素材，要按"是不是原生匹配分辨率"选。**

### 三种能用的形态

| 形态 | 适合什么 | 怎么出 |
|---|---|---|
| **横穿剪影** | 单个角色/动物，从右走到左 | `make x.gif`（默认 `travel`） |
| **原地走 + 背景滚动** | 像素角色；循环连续、不"闪现" | `make x.png --row N`（精灵表） |
| **整帧铺满** | 本身就是宽幅的动画 | `make x.gif --mode scene --fit height` |

> 为什么角色行走推荐"原地走 + 背景滚动"：20 帧内让角色横穿 256px 会快到像瞬移；
> 原地循环 + 背景滚动才有"一直在走"的连续感，而且首尾天然接得上。

---

## 2. 准备素材

素材放 `gifs/` 下（`gifs/oga/` 放精灵表，其他自便）。**两张表就够开工**：
`Pepper&Carrot` 的 5 张角色表已经在 `gifs/oga/`，可直接用。

### 2.1 精灵表（推荐）

要求：

- 角色格子按**规则网格**排列，每格尺寸一致（本项目用 24×32）；
- **每行一个朝向，每列一个行走帧**；
- 底色是**纯色**（单色或双色都行，工具会处理）。

拿到一张表先**看结构**，不要猜：

```bash
python pixelbar.py sheet "gifs/oga/carrot..png" --preview gifs/check.png
```

输出会直接告诉你每行是什么、有多大、有没有内容：

```
carrot..png  网格 3x4  每格 24x32  原点 (0, 0)
  row0: 内容 12x21px，每帧前景 [148, 156, 148] 像素     ← 正面/背面
  row1: 内容 22x19px，每帧前景 [198, 186, 200] 像素     ← 侧视（横着走用这行）
  row2: 内容 12x21px，每帧前景 [143, 151, 142] 像素
  row3: 内容 22x19px，每帧前景 [200, 186, 198] 像素
```

**怎么判断哪一行是侧视**：内容**更宽更矮**的那几行（侧视角色是横着的）。
再看 `--preview` 出的图确认。

如果网格不是 3×4 / 24×32，用 `--cell 32x32 --cols 4 --rows 4 --origin 0,0` 指定。

### 2.2 GIF

三个坑（工具已自动处理，但你得知道为什么有的 GIF 出来是黑块）：

| 坑 | 症状 | 工具怎么处理 |
|---|---|---|
| 透明背景 GIF 的透明像素在 RGB 里是黑/白 | 整块背景被当前景，出来一片实心方块 | **优先看 alpha 通道** |
| 不透明但纯色底（白底/洋红底） | 同上 | 采样边框推底色并剔除 |
| 只取前 20 帧 | 长循环动画只播了开头三分之一 | **均匀抽样覆盖整个循环** |

先看效果再决定：

```bash
python pixelbar.py make x.gif --preview gifs/check.png --dry
```

---

## 3. 制作

### 3.1 精灵表 → 动画

```bash
python pixelbar.py make "gifs/oga/carrot..png" --row 1 \
    --preview gifs/cat.png --export gifs/anime/
```

### 3.2 GIF → 动画

```bash
python pixelbar.py make horse.gif --preview gifs/horse.png --export gifs/anime/
```

### 3.3 调参速查：什么时候调哪个

| 现象 | 调什么 |
|---|---|
| 前景抓不全 / 抓多了 | `--thr 0-255`（默认 128）；素材是暗底亮物加 `--invert` |
| 背景整块变成前景 | 加 `--no-bg` 关掉底色剔除，或改用透明背景的素材 |
| 角色太小/太扁 | `--target-h`（GIF 用，默认 28）；精灵表是原生的，不要缩放 |
| 角色位置不对 | `--x N`（左边缘列）；`--flip` 水平翻转 |
| 背景太吵、盖过角色 | `--style ground`（最干净）；可选 `hills/skyline/stars/petals` |
| 循环处"卡一下" | 见下方 §6「循环不无缝」 |
| 底部有说明文字 | `--trim-bottom N` 裁掉源图底部若干行 |

### 3.4 加进动画库（改 JSON，不用改代码）

动画库是**声明式**的：`pixelbar/anims.json`。改它就能增删动画。

```json
{
  "anims": {
    "my_cat": {
      "label": "我的猫",
      "slot": null,
      "style": "ground",
      "actors": [{"sheet": "carrot", "row": 1, "x": 116}]
    }
  }
}
```

- `slot` 给 2-6 的数字 = 参与 `anims --burn` 的默认烧录；给 `null` = 只在库里
- 多个 `actors` = 同屏多角色（`duo` 就是 Pepper + 猫）
- 想放自己的素材：先在 `sheets` 里加一张表，再让 `actors` 引用它的名字
- **不想改内置文件**：另存一份 JSON，用 `--recipe 我的.json` 追加（后者覆盖前者）

改完验证：

```bash
python pixelbar.py anims --list        # 看新动画在不在、映射对不对
python pixelbar.py anims my_cat --preview p.png   # 出预览
```

---

## 4. 上机

### 4.1 铁律：先预览，再上机

**永远先 `--preview` 看图，再推设备。** 原因很实在：设备**没有屏幕内容读回接口**
（0xEE 只能确认类别/槽位，不能确认内容），推错了你只能靠肉眼在设备上发现，
而调试一次可能要重推 18 帧 × 1064 字节。

### 4.2 单张推送

```bash
python pixelbar.py make "gifs/oga/carrot..png" --row 1 --category 2
```

### 4.3 批量烧录（**分批，别一次推 5 个**）

```bash
python pixelbar.py anims --burn --only cat duo     # 一次两个，稳
python pixelbar.py anims --burn --only parade      # 再来一批
```

固件在提交 flash 时需要时间；连推太密会**卡死**（见 §6）。默认 `--settle 4 --gap 1`
已经留足，不要为了快把它们调小。

### 4.4 切换（这才是日常用的）

烧录是一次性的慢操作；之后切换只发一条 `0xEF`，**约 2ms**：

```bash
python pixelbar.py anims cat
python pixelbar.py anims duo
```

这是本项目的关键设计：**把"慢的上传"和"快的切换"分开**。

---

## 5. 验证

### 5.1 协议层（机器可验）

```bash
python pixelbar.py status          # 看「类别 / 槽位」是不是你期望的
```

批量核对：切换后回读类别，应逐个对上（`tools/verify_switch.py` 就是干这个的）。

### 5.2 肉眼层（**必须做，机器替不了**）

因为无内容读回，**最后一步一定要看屏**。看三件事：

1. **认得出主体吗**？认不出就是素材分辨率不够（回 §1 换素材）。
2. **循环处卡吗**？卡就是无缝约束没满足（见 §6）。
3. **角色有没有被背景吃掉**？糊在一起就是背景填实了（见 §6）。

### 5.3 导出 GIF 存档

```bash
python pixelbar.py anims --export gifs/anime/
```

导出的是**上屏后的真实点阵**（256×32、无限循环），所以 GIF 和屏上看到的是同一份内容。
GIF 的 comment 段已写入 CC-BY 署名。

---

## 6. 故障处理（按症状查）

### 设备卡死：命令全超时、屏不动

**症状**：设备**持续刷** `2f bb ec 17 00 04 00 03 <seq>`（seq 每秒涨十几个），
HID 写返回 -1，`status` 也超时。

**处理**：**只能断电重启** —— 拔插 USB-C 数据线，或把音箱关机再开。软件救不回来。

**根因**：数据阶段的 ACK 没校验块序号，上一次上传的残留 ACK 被当成本次的 ACK，
块号错位后固件卡在等某一块。

**已做的防护**（正常用不会撞上）：
- 上传前 `assert_link_healthy()` 体检，发现设备在刷 ACK 就直接报错并提示断电，
  而不是继续发帧把它搞得更乱；
- 数据 ACK 校验序号；
- `anims --burn` 默认留 4s 提交时间、支持 `--only` 分批。

### 图不显示 / 显示的还是设备原生动画

- **category 7（cyber）不能存自定义图**，切过去会显示设备原生循环动画。
  可用的是 **category 2-6**（已逐类实测）。
- 上传后必须再发 `0xEF 02 <cat> <tpl> FF` 才真正显示（本工具已自动发）。
- 协议 ACK 成功 **≠** 图写进去了。排查时用**大号数字 / 边框**这类不可认错的测试图
  逐类验证，别靠猜。

### 循环处"卡一下"

两条硬约束必须同时满足：

1. **输出帧数取走姿帧数的整数倍** —— 3 帧走姿 → 用 18 帧（不是 20）。否则最后一帧
   到第一帧的走姿会**倒退**。
2. **背景每帧位移 = 背景周期 ÷ 帧数** —— 否则地面虚线/远山会在循环处跳变。

工具默认已满足（`--frames 18`、背景速度自动算）。**自己改帧数时要重新检查这两条**。

### 角色被背景吃掉

1 位屏上，**背景必须只画轮廓**（地面线、远山轮廓、稀疏星点）。一旦背景填实，
它和同样是实心的角色就糊成一片，角色直接消失。

用 `--style ground` 最干净；`hills/skyline/stars/petals` 也已按"只画轮廓、稀疏"实现。

### 精灵表切出来每格全白

底色采样失败，退化成亮度阈值把整块背景当前景了。**多色底图**（如 Pepper&Carrot 的
青绿角色区 + 灰色人像区）会触发。工具已改为**在要切的网格区域内**取颜色众数当底色；
自己写脚本时注意这点。

---

## 7. 完整命令速查

```bash
# 启动
python pixelbar.py doctor                      # 预检（唯一入口）
python pixelbar.py selftest                    # 离线自检 52 项
python pixelbar.py status                      # 设备状态

# 看素材
python pixelbar.py sheet 表.png --preview p.png     # 精灵表结构与逐行预览
python pixelbar.py make  x.gif --preview p.png --dry # GIF 先看效果

# 制作
python pixelbar.py make 表.png --row 1 --export out/          # 精灵表 → 动画
python pixelbar.py make x.gif  --export out/                  # GIF → 动画
python pixelbar.py anims --export out/                        # 导出全部内置动画

# 上机
python pixelbar.py make 表.png --row 1 --category 2           # 单张推送
python pixelbar.py anims --burn --only cat duo                # 分批烧录
python pixelbar.py anims cat                                  # 切换（约 2ms）

# 其他
python pixelbar.py anims --list                # 动画库清单与槽位映射
python pixelbar.py anims --demo                # 依次演示
python pixelbar.py text "你好"                 # 设备字体文本
python pixelbar.py play 目录 --spectrum 1      # 放音乐 + 屏上频谱
```

---

## 附：给别人复现这份流程

1. `python pixelbar.py doctor` —— 缺什么它都会说，且给修法；
2. 素材：`gifs/oga/` 里 5 张 Pepper&Carrot 角色表（**CC-BY，须署名 David Revoy**）；
3. `python pixelbar.py anims --export out/` —— 立刻拿到 5 个 256×32 的 GIF 成品；
4. 想自己做新的：照 §2 → §3 走一遍，全程不用改代码（改 `anims.json` 即可）。
