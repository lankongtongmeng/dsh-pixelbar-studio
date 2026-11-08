# dsh-pixelbar-studio

把**花再 Halo PixelBar** 的 256×32 点阵屏变成 DSH 里可创作的画布——
推自定义位图、GIF 动画、像素角色行走场景、点阵表情，并带颜色校准、环境自检与制作管线。

> 独立社区项目，与漫步者（EDIFIER）无关联。设备标识 `VID 0x2D99 / PID 0xA106`（A106 面板）。

## 它和 `dsh-pixelbar` 有什么不同

同一台设备上已经有一个 DSH 插件
[SilverlingFox/dsh-pixelbar](https://github.com/SilverlingFox/dsh-pixelbar)，做的是
**文字 / 场景 / 屏色 / 氛围灯 / 音量 / 推完回时钟**。两者**不冲突**：

| | `dsh-pixelbar` | **本插件** |
| --- | --- | --- |
| 定位 | 通知与灯控 | **创作与内容**（也覆盖基础控制） |
| 推文字 | ✅ | ✅（自渲染，支持中文点阵） |
| 内置场景 / 时钟 / 频谱 | ✅ | ✅ |
| 屏色 / 氛围灯 / 音量 | ✅ | ✅（**屏色与灯色自动套颜色校准**） |
| 推完自动回时钟 | ✅（默认 15s） | ✅（默认不回，见下） |
| **自定义位图（`0x17`）** | ❌ | ✅ |
| **GIF → 点阵动画** | ❌ | ✅ |
| **精灵表 / 多角色行走场景** | ❌ | ✅ |
| **声明式动画配方 + 导出 GIF** | ❌ | ✅ |
| 表情槽位 | ❌ | ✅ |
| **颜色校准表 + 色卡重校准** | ✅（有校准） | ✅（可自己重测） |
| 制作管线 / 环境自检 | ❌ | ✅ |

**社区所有开源实现（SDK / 插件 / 歌词工具）都无法推自定义位图或动画**，这是本插件的核心增量。

> 两个插件会写同一个 HID 设备，**不建议同时跑**。只装一个即可。

**关于「推完自动回时钟」的默认值**：本插件默认**不回**（`clock_after: 0`），因为它是创作工具
——你推上去的动画应该留在屏上。当通知用就显式传 `clock_after: 15`。

## 能力

- **推图**：任意图片 → 256×32 单色点阵（自动缩放、极性取反、包围盒裁剪）
- **推动画**：GIF → 逐帧转码 + 上传（槽位上限 20 帧 / 21280 字节）
- **角色动画**：精灵表切片 → 多角色同屏 + 背景无缝滚动；切换只要约 2ms
- **表情**：6 种点阵表情，一次性烧入、运行时瞬时切换
- **制作管线**：`make` / `sheet` 看结构、出预览、导出 GIF（导出会把 CC-BY 署名写进 GIF）
- **颜色校准**：这块屏 **R 通道增益弱、B 偏强**，含红的颜色直接发会偏青/偏紫 →
  屏色 / 场景色 / 氛围灯色默认自动查表补偿；`calib --card` 可推色卡自己重测
- **推完自动回时钟**：`--clock-after SEC` 让内容 N 秒后自动让位给时钟（脱离式子进程实现）
- **环境自检**：`doctor` 逐项检查依赖 / 字体 / 素材 / 设备链路，**每项给修法**
- **硬件 EQ**：音箱自带的 19 种音效模式

## 安装

三种方式任选。

**① DSH 插件市场**（推荐）：插件 → 发现 → 搜 `dsh-pixelbar-studio`。

**② npm**

```powershell
npm install dsh-pixelbar-studio
```

然后把 `dsh-pixelbar-studio` 加进 `%USERPROFILE%\.dsh\profiles\<profile>\package.json` 的
`dsh.profile.bundles` 数组，重启 DSH。包里的 `package.json` 已声明
`dsh.bundle.patch`，DSH 会据此加载。

**③ 手动**：把包解到 profile 的 `node_modules\dsh-pixelbar-studio`，再加进
`dsh.profile.bundles`，重启 DSH。

**④ 本地安装脚本**（从源码目录装，**不跑 `npm install`**，因此不会动到 profile 的依赖树）

```powershell
node tools/install_to_dsh.mjs              # 装到默认 profile
node tools/install_to_dsh.mjs --dry        # 只看会做什么
node tools/install_to_dsh.mjs --profile <目录>
node tools/install_to_dsh.mjs --uninstall  # 回滚
```

脚本只做两件事：复制文件 + 往 `dsh.profile.bundles` 追加一行（原 `package.json`
会备份成 `package.json.bak-before-pixelbar`）。装完用
`node tools/verify_install.mjs` 可以验证**装好的那一份**能独立工作。

装完在会话里说一句「看看 PixelBar 状态」就能验证——模型会调用 `pixelbar_status`。

## 环境要求

- **Python 3.10+**，且装好两个包：

  ```powershell
  python -m pip install hidapi pillow
  ```

  ⚠️ PyPI 上的 `hid` 包在本机缺 `hidapi.dll`、`import` 必报错——**包名是 `hidapi`**。

- **USB-C 数据线**（不是充电线）。蓝牙只走音频、不承载 HID，仅蓝牙连接时枚举不到控制接口。
- 已在 **Windows 11** 实测。其它平台未验证（Python 侧可移植，`run.cmd` 是 Windows 专用）。
- 解释器不在 PATH 时，用环境变量 `DSH_PIXELBAR_PYTHON` 指定绝对路径。

**装完第一件事：跑 `pixelbar_doctor`。** 它会把上面每一条逐项检查并给出修法。

## 工具

| 工具 | 作用 |
| --- | --- |
| `pixelbar_doctor` | 环境体检（依赖 / 字体 / 素材 / 设备链路），每项给修法 |
| `pixelbar_status` | 读设备状态（音量、氛围灯、文本、屏主题色与当前类别/槽位） |
| `pixelbar_show` | 推图片 / GIF 上屏；不给文件则推**满边框对齐自检图** |
| `pixelbar_anim` | 角色动画：list / switch / burn / export / demo |
| `pixelbar_make` | 一键制作：GIF 或精灵表 → 预览 / 导出 GIF / 上机 |
| `pixelbar_sheet` | 看精灵表结构、逐行内容尺寸、预览某一行走起来什么样 |
| `pixelbar_faces` | 表情：list / switch / burn / demo |
| `pixelbar_device` | 基础控制：屏色 / 场景 / 时钟 / 频谱 / 氛围灯 / 音量 |
| `pixelbar_calib` | 颜色校准表；`card` 推色卡做目测重校准 |
| `pixelbar_eq` | 音箱自带的 19 种硬件音效模式 |
| `pixelbar_text` | 把文字自渲染成点阵（支持中文、多行） |

## 例子

```
pixelbar_doctor {}
pixelbar_show  { "file": "D:\\pic\\cat.gif", "category": 2, "preview": "D:\\pic\\preview.png" }
pixelbar_show  { "file": "D:\\pic\\note.png", "clock_after": 15 }
pixelbar_anim  { "action": "list" }
pixelbar_anim  { "action": "switch", "name": "duo" }
pixelbar_make  { "source": "D:\\art\\hero.png", "row": 0, "preview": "D:\\art\\p.png" }
pixelbar_text  { "lines": ["在"], "cjk": true }
pixelbar_device { "action": "color", "rgb": "F0B4C8" }
pixelbar_calib { "card": true, "dwell": 3 }
```

**先预览、再上机。** 不指定 `category` 时 `pixelbar_make` 只在本地出预览与导出，
绝不碰设备。

## 安全边界

- **不暴露 `raw`（发送任意 HID 帧）。** 文本帧的 byte4 置错会让设备解析出 261 字节长度，
  而整包只有 64 字节 → **固件挂死，必须给音箱断电才能恢复**。工具只暴露经过实机验证的命令。
- 只匹配 `VID 0x2D99 / PID 0xA106` + 控制接口 `usage_page 0xFF14 / usage 1`。
- 不读凭据、不碰固件升级、不做工厂重置。

## 已知限制（请先读）

- **屏幕内容无法读回。** 官方查询函数只返回配置，`0xEE` 只能确认类别/槽位。
  所以**无法程序化验证「图有没有写进去」**，只能靠人眼看屏，或推 `border` 满边框自检图。
- **颜色校准只做精确匹配、不做插值。** 校准值是目测实测的锚点，没命中的颜色原样发送
  （插值没有实测依据，可能比不校准更糟）。想覆盖更多颜色就用 `calib --card` 自己重测。
  ⚠️ 校准表**不是幂等的**（黄 `#FFFF00`→`#FF8800`，而 `#FF8800` 又是橙的锚点），
  所以**只能应用一次**——CLI 里只在设置颜色那一步做一次。
- **`category 7` 是死槽**：写进去会回落到设备原生动画，自定义图不显示。可用的是 2–6。
  （`pixelbar_faces` 的 `celebrate` 落在 7，属已知遗留问题。）
- **固件可能卡死在数据接收态**：连推多个多帧动画时若 ACK 块号错位会卡死，表现是设备
  持续刷状态、`write` 返回 −1、所有命令超时。**软件无法恢复，拔插 USB-C 数据线即可。**
  工具已做防护（上传前链路体检、ACK 校验块号、烧录留冷却），但仍建议**分批烧**。
- **槽位上限 20 帧 / 21280 字节**，超限要抽帧。
- **A160 的校准参数不适用 A106**：本机无需任何横向补偿。
- **不要用软件 EQ**：本项目自写的 biquad 未通过验证，已放弃；音色只走设备侧。

详细的坑与判据见 **[docs/PITFALLS.md](docs/PITFALLS.md)**——这份文档记的都是真踩过、
能复现的问题，按代价排序。

## 文档

| 文件 | 内容 |
| --- | --- |
| [docs/PITFALLS.md](docs/PITFALLS.md) | **踩坑与经验包**（协议 / 渲染 / 素材 / 工具链 / 音频 / 方法论） |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | 制作流程 SOP（启动 → 选素材 → 制作 → 上机 → 验证） |
| [docs/README.md](docs/README.md) | 命令行工具包完整手册（26 个子命令） |
| [docs/PROTOCOL.md](docs/PROTOCOL.md) | 协议细节（以此为准） |
| [docs/REFERENCES.md](docs/REFERENCES.md) | 来源分级、方法论复盘、与社区的相对位置 |
| [NOTICE.md](NOTICE.md) | 第三方署名与授权 |

本插件自带的 Python 工具包也可以**脱离 DSH 单独用**：

```powershell
run.cmd                    :: 无参数 = 环境预检
run.cmd selftest           :: 72 项离线自检（不连设备）
run.cmd anims --list       :: 列出动画
run.cmd calib              :: 打印颜色校准表
run.cmd image cat.png --clock-after 15   :: 推图，15 秒后自动回时钟
```

## 许可与署名

- 本仓库代码：**MIT**（见 [LICENSE](LICENSE)）
- **Pepper&Carrot 角色素材：CC-BY 4.0/3.0，作者 David Revoy，必须署名**（见 [NOTICE.md](NOTICE.md)）
- 颜色校准表：来自 `SilverlingFox/dsh-pixelbar`（MIT）的目测校准数据
- 5×7 字库：MIT（`3441293738/claude-edifier-pixelbar-usage`）
- 自检用官方抓包 OUT 帧：MIT（`ethan71950701/PixelBar-Display-Hook`）

**免责**：本项目与漫步者（EDIFIER）无关联、未获其背书或支持。逆向工作基于本机自有设备
与官方 PC 端程序的本地观察，未包含任何官方二进制、反编译产物、凭据或固件。
