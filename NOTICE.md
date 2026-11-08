# 第三方作品与署名

本仓库以 MIT 授权发布（见 `LICENSE`），但包含下列第三方作品。它们**不受 MIT 覆盖**，
各自的授权与署名义务如下。

---

## 1. Pepper&Carrot 24×32 角色素材 —— CC-BY，**必须署名**

- **文件**：`gifs/oga/Pepper_publish..png`、`carrot..png`、`coriander_publish..png`、
  `saffron_publish..png`、`shichimi_publish..png`
- **作者**：David Revoy
- **来源**：<https://opengameart.org/content/24x32-peppercarrot-characters>
  （改编自其网络漫画 *Pepper&Carrot* 的线稿）
- **授权**：**CC-BY 4.0 / CC-BY 3.0 —— 必须署名，不是 CC0**
  （作者声明非商业用途可免署名，但仍应注明 David Revoy）

**本项目做的改动**：仅按 24×32 网格切片、二值化为 1-bit、并合成到 256×32 画布；
未修改原始 PNG。`anims --export` 导出 GIF 时会把署名写进 GIF 的 comment 段。

---

## 2. 5×7 ASCII 字库 —— MIT

- **文件**：`pixelbar/font5x7.py`
- **来源**：<https://github.com/3441293738/claude-edifier-pixelbar-usage>（MIT，42 个字形）

**说明**：只取用了字库本身，**没有沿用该项目的编码实现**——它的 `encode_pixel_bin`
用的是社区 wafer 那套错误的「20 字节 unit 头」（见 `docs/PITFALLS.md` 1.1）。

---

## 3. 官方抓包 OUT 帧 —— MIT

- **文件**：`wiretest/captures.json`
- **来源**：<https://github.com/ethan71950701/PixelBar-Display-Hook>（MIT）的
  `tests/fixtures/captured_uploads.json`

**本项目做的改动**：只抽出 capture 20 / 21 / 23 的 **OUT 帧**（本项目自检与 `replay`
真正用到的部分），**去掉了设备回包（`in`）与图像 hex**。文件体积从 34KB 降到 13KB。
抽取脚本：`tools/make_fixture.py`。

这些帧是设备协议的事实性数据，用来做逐字节回归测试——本项目对 capture 20/21/23
的复现是整条链路的锚点。

---

## 4. 参考但未复制代码的项目

下列项目用于**协议交叉验证与设计参考**，本仓库未包含其代码：

| 项目 | 用途 |
| --- | --- |
| [XFEstudio/HaloPixelToolBox](https://github.com/XFEstudio/HaloPixelToolBox)（MIT） | 协议交叉验证 |
| [Serius117/wafer_pixelbar_public](https://github.com/Serius117/wafer_pixelbar_public)（MIT） | 表情槽位架构**思路**参考（代码自研）。注意其槽位映射与横向补偿取自 **A160**，不适用于本机 A106 |
| [woozyc/pixelbardiy](https://github.com/woozyc/pixelbardiy) | 证实原厂 `0x17` 是资源保存路径；其 HPL2 实时流方案未采用 |
| [FerrinWang/pixelbar-studio](https://github.com/FerrinWang/pixelbar-studio) | 1064 格式交叉验证 |
| [OpenRGB](https://github.com/CalcProgrammer1/OpenRGB)（`EdifierHaloController`） | 主题色与内置场景交叉验证 |

---

## 5. 相关项目（同一设备的 DSH 插件，非本仓库内容）

[SilverlingFox/dsh-pixelbar](https://github.com/SilverlingFox/dsh-pixelbar)（MIT）是同一设备的
另一个 DSH 插件，做**文字 / 场景 / 屏色（含颜色校准）/ 氛围灯 / 音量 / 推完回时钟**。
本插件与它**不冲突、也不重复**：本插件聚焦**自定义位图与动画**（`0x17` 能力），
这是它与社区所有实现都缺的部分。

它的两项实测成果值得后续借鉴：本屏颜色校准表（R 偏弱、B 偏强）与「推完自动回时钟」。

---

## 免责声明

本项目是**独立的社区项目**，与漫步者（EDIFIER）无关联、未获其背书或支持。
逆向工作基于本机自有设备与官方 PC 端程序的本地观察，未包含任何官方二进制、
反编译产物、凭据或固件。
