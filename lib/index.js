// dsh-pixelbar-studio · Host 半边
//
// 把 halo-pixelbar 的 Python 工具包桥接成 DSH 工具，让模型能直接往
// 花再 Halo PixelBar 的 256×32 点阵屏推自定义位图 / 动画 / 像素角色场景。
//
// 为什么是「Node 薄壳 + 短命 Python 进程」而不是全 Node 重写：
//   渲染依赖 Pillow、通信依赖 hidapi，重写不划算；薄壳每次调用约 70–140ms，够用。
//   同生态的 dsh-pixelbar 也是这个架构，实测可用。
//
// 安全边界：**不暴露 `raw`（任意 HID 帧）**。写错一个字节就可能把固件打进挂死态、
//   必须给音箱断电才能恢复（见 docs/PITFALLS.md 1.2）。工具只暴露经过验证的命令。
import { spawn } from 'node:child_process'
import { isAbsolute, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const SCRIPT = join(ROOT, 'pixelbar.py')

export const name = 'pixelbar-studio'
export const inject = ['tools']

// ---------------------------------------------------------------- Python 桥

// 解释器候选：环境变量优先，其次 Windows 上最可靠的 py 启动器，再退到 PATH。
const PYTHONS = [process.env.DSH_PIXELBAR_PYTHON, 'py', 'python', 'python3'].filter(Boolean)

function spawnOnce(py, argv, timeoutMs) {
  return new Promise((resolve, reject) => {
    let child
    try {
      child = spawn(py, [SCRIPT, ...argv], {
        cwd: ROOT,
        windowsHide: true, // 不闪黑框
        env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
      })
    } catch (e) {
      reject(e)
      return
    }
    let out = ''
    let err = ''
    let settled = false
    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      try { child.kill() } catch { /* 已经退了 */ }
      reject(new Error(`pixelbar 超时（${Math.round(timeoutMs / 1000)}s）：${argv.join(' ')}`))
    }, timeoutMs)
    child.stdout.on('data', (d) => { out += d })
    child.stderr.on('data', (d) => { err += d })
    child.on('error', (e) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      reject(e)
    })
    child.on('close', (code) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      const text = `${out}${err ? (out ? '\n' : '') + err : ''}`.trim()
      if (code === 0) resolve(text)
      else reject(new Error(text || `pixelbar 退出码 ${code}`))
    })
  })
}

async function runPy(argv, timeoutMs) {
  let missing = 0
  for (const py of PYTHONS) {
    try {
      return await spawnOnce(py, argv, timeoutMs)
    } catch (e) {
      if (e && e.code === 'ENOENT') { missing += 1; continue }
      throw e
    }
  }
  throw new Error(
    `找不到可用的 Python 解释器（试过 ${PYTHONS.join(' / ')}）。` +
    '装 Python 3.10+ 后执行 `python -m pip install hidapi pillow`；' +
    '或用环境变量 DSH_PIXELBAR_PYTHON 指定解释器绝对路径。' +
    `（已探测失败 ${missing} 个候选；先跑 pixelbar_doctor 能看到具体缺什么。）`,
  )
}

// ---------------------------------------------------------------- 工具脚手架

const str = (description, extra = {}) => ({ type: 'string', description, ...extra })
const int = (description) => ({ type: 'integer', description })
const bool = (description) => ({ type: 'boolean', description })

const TEXT_OUT = {
  schema: {
    type: 'object',
    additionalProperties: false,
    required: ['text'],
    properties: { text: { type: 'string' } },
  },
  render: (_args, v) => [{ type: 'text', text: v.text }],
}

/** 有值才加，避免把 undefined 拼成 "--flag undefined"。 */
function push(argv, flag, value) {
  if (value === undefined || value === null || value === '') return
  argv.push(flag, String(value))
}
function on(argv, flag, yes) {
  if (yes) argv.push(flag)
}
/** 文件参数一律要求绝对路径：插件进程的 cwd 与用户当前目录不是一回事。 */
function abs(p, label = 'path') {
  if (!isAbsolute(p)) throw new Error(`${label} 要用绝对路径，收到：${p}`)
  return p
}

function cliTool({ name, description, parameters, argv, timeoutMs = 180000 }) {
  return {
    name,
    description,
    parameters,
    timeoutMs,
    output: TEXT_OUT,
    async execute(args = {}) {
      return { text: await runPy(argv(args), timeoutMs) }
    },
  }
}

// ---------------------------------------------------------------- 工具集

const doctorTool = cliTool({
  name: 'pixelbar_doctor',
  description:
    'PixelBar 环境体检：Python / hidapi / Pillow / 中文字体 / 素材 / 设备链路逐项检查，' +
    '每一项都给出可照做的修法。任何 PixelBar 操作失败时先跑这个。',
  parameters: {
    type: 'object',
    additionalProperties: false,
    properties: { offline: bool('只检查本机依赖与素材，不碰设备') },
  },
  argv: (a) => {
    const v = ['doctor']
    on(v, '--offline', a.offline)
    return v
  },
  timeoutMs: 60000,
})

const statusTool = cliTool({
  name: 'pixelbar_status',
  description: '读 PixelBar 当前状态：硬件音量、氛围灯、文本、像素屏的主题色与当前类别/槽位。',
  parameters: { type: 'object', additionalProperties: false, properties: {} },
  argv: () => ['status'],
  timeoutMs: 30000,
})

const showTool = cliTool({
  name: 'pixelbar_show',
  description:
    '把一张图片或 GIF 推到 PixelBar 的 256×32 单色点阵屏（自动缩放、二值化）。' +
    '不传 file 时推「1px 满边框对齐自检图」，用来确认屏幕没有横向偏移——' +
    '这是唯一可靠的验证手段，因为设备**不支持读回屏幕内容**。',
  parameters: {
    type: 'object',
    additionalProperties: false,
    properties: {
      file: str('图片或 GIF 的绝对路径。.gif 走动画管线，其它按静态图处理；省略则推对齐自检图'),
      category: int('写到哪个场景类别，默认 2。2-6 可用；7 是死槽（会回落到原生动画），不要用'),
      option: int('槽位，默认 0'),
      preview: str('同时把渲染结果写成预览 PNG 的路径（本地检查用，推荐）'),
      dry: bool('只编码不推送，先看预览再上机'),
    },
  },
  argv: (a) => {
    const v = []
    if (!a.file) v.push('border')
    else if (/\.gif$/i.test(a.file)) v.push('anim', abs(a.file, 'file'))
    else v.push('image', abs(a.file, 'file'))
    push(v, '--category', a.category)
    push(v, '--option', a.option)
    push(v, '--preview', a.preview)
    on(v, '--dry', a.dry)
    return v
  },
})

const animTool = cliTool({
  name: 'pixelbar_anim',
  description:
    '二次元角色动画。list 列出配方里全部动画；switch 切到某个（约 2ms，无需重新上传）；' +
    'burn 把动画烧进设备槽位（慢，每个要等固件写 flash）；export 导出成 GIF；demo 依次演示。' +
    '注意：switch 只能切到**已经烧过**的动画。',
  parameters: {
    type: 'object',
    additionalProperties: false,
    required: ['action'],
    properties: {
      action: str('list=列出；switch=切换；burn=烧录；export=导出 GIF；demo=依次演示', {
        enum: ['list', 'switch', 'burn', 'export', 'demo'],
      }),
      name: str('action=switch 时的动画名，如 cat / duo / parade / town / night'),
      only: {
        type: 'array',
        items: { type: 'string' },
        description: 'action=burn 时只烧这几个。逐个/分批烧更稳，连推多个有把固件卡死的风险',
      },
      export: str('action=export 时的输出目录绝对路径'),
      frames: int('帧数，默认 18。要无缝循环就得是走姿帧数（3）的整数倍'),
      dry: bool('只算不推'),
    },
  },
  argv: (a) => {
    const v = ['anims']
    if (a.action === 'list') v.push('--list')
    else if (a.action === 'burn') v.push('--burn')
    else if (a.action === 'demo') v.push('--demo')
    else if (a.action === 'export') {
      if (!a.export) throw new Error('action=export 需要 export（输出目录绝对路径）')
      v.push('--export', abs(a.export, 'export'))
    } else if (a.action === 'switch') {
      if (!a.name) throw new Error('action=switch 需要 name（动画名）')
      v.push(a.name)
    }
    if (Array.isArray(a.only) && a.only.length) v.push('--only', ...a.only)
    push(v, '--frames', a.frames)
    on(v, '--dry', a.dry)
    return v
  },
  timeoutMs: 900000,
})

const makeTool = cliTool({
  name: 'pixelbar_make',
  description:
    '一键制作：把 GIF 或精灵表做成屏上能播的东西——出预览图 / 导出 GIF / 直接上机。' +
    '不指定 category 时只在本地产出，**绝不碰设备**。做新素材从这里开始。',
  parameters: {
    type: 'object',
    additionalProperties: false,
    required: ['source'],
    properties: {
      source: str('源文件绝对路径：.gif 或精灵表 PNG'),
      kind: str('源类型，默认按扩展名判断', { enum: ['auto', 'gif', 'sheet'] }),
      row: int('精灵表用哪一行朝向（0-3）。用 pixelbar_sheet 先看哪一行是侧视'),
      style: str('背景风格', { enum: ['ground', 'hills', 'skyline', 'stars', 'petals'] }),
      x: int('角色左边缘列（默认居中）'),
      flip: bool('水平翻转'),
      frames: int('帧数，默认 18'),
      preview: str('预览图输出路径（强烈建议给，先看再上机）'),
      export: str('导出 GIF 的路径或目录'),
      category: int('推到该类别（2-6）。不填则不上机'),
      dry: bool('只算不推'),
    },
  },
  argv: (a) => {
    const v = ['make', abs(a.source, 'source')]
    push(v, '--kind', a.kind)
    push(v, '--row', a.row)
    push(v, '--style', a.style)
    push(v, '--x', a.x)
    on(v, '--flip', a.flip)
    push(v, '--frames', a.frames)
    push(v, '--preview', a.preview)
    push(v, '--export', a.export)
    push(v, '--category', a.category)
    on(v, '--dry', a.dry)
    return v
  },
  timeoutMs: 300000,
})

const sheetTool = cliTool({
  name: 'pixelbar_sheet',
  description:
    '看一张精灵表的结构：网格怎么切、每一行内容占多大、以及某一行走起来什么样。' +
    '给新角色做动画前先用它确认表结构和朝向行（走姿通常在同一行里横向排列）。',
  parameters: {
    type: 'object',
    additionalProperties: false,
    required: ['file'],
    properties: {
      file: str('精灵表 PNG 的绝对路径'),
      cell: str('每格宽x高，如 "24x32"（也接受 24,32）'),
      cols: int('列数'),
      rows: int('行数'),
      origin: str('网格左上角偏移，如 "0x0"'),
      row: int('只看这一行（不填则逐行列出）'),
      style: str('背景风格', { enum: ['ground', 'hills', 'skyline', 'stars', 'petals'] }),
      frames: int('预览帧数，默认 18'),
      preview: str('预览图输出路径'),
    },
  },
  argv: (a) => {
    const v = ['sheet', abs(a.file, 'file')]
    push(v, '--cell', a.cell)
    push(v, '--cols', a.cols)
    push(v, '--rows', a.rows)
    push(v, '--origin', a.origin)
    push(v, '--row', a.row)
    push(v, '--style', a.style)
    push(v, '--frames', a.frames)
    push(v, '--preview', a.preview)
    return v
  },
})

const facesTool = cliTool({
  name: 'pixelbar_faces',
  description:
    '点阵表情：list 列出映射；switch 切到某个（约 2ms）；burn 烧进设备槽位；demo 依次演示。' +
    '注意 celebrate 落在 category 7 —— 那是**死槽**，烧进去不会显示（已知遗留问题）。',
  parameters: {
    type: 'object',
    additionalProperties: false,
    required: ['action'],
    properties: {
      action: str('list=列出；switch=切换；burn=烧录；demo=依次演示', {
        enum: ['list', 'switch', 'burn', 'demo'],
      }),
      name: str('action=switch 时的表情名', {
        enum: ['normal', 'happy', 'sad', 'angry', 'thinking', 'celebrate'],
      }),
      dry: bool('只算不推'),
    },
  },
  argv: (a) => {
    const v = ['faces']
    if (a.action === 'list') v.push('--list')
    else if (a.action === 'burn') v.push('--burn')
    else if (a.action === 'demo') v.push('--demo')
    else if (a.action === 'switch') {
      if (!a.name) throw new Error('action=switch 需要 name（表情名）')
      v.push(a.name)
    }
    on(v, '--dry', a.dry)
    return v
  },
  timeoutMs: 600000,
})

const eqTool = cliTool({
  name: 'pixelbar_eq',
  description:
    '音箱自带的硬件 EQ 音效模式（19 种）：list 列出全部，set 切到某个。' +
    '这是设备侧音效，与软件 EQ 无关（本项目已放弃自写软件 EQ，见 docs/PITFALLS.md 5.4）。',
  parameters: {
    type: 'object',
    additionalProperties: false,
    required: ['action'],
    properties: {
      action: str('list=列出全部音效；set=切到某个', { enum: ['list', 'set'] }),
      name: str('action=set 时的音效名 / 别名 / 编号，如 high / 高频增强 / 19'),
    },
  },
  argv: (a) => {
    if (a.action === 'list') return ['eq', '--list']
    if (!a.name) throw new Error('action=set 需要 name（音效名 / 别名 / 编号）')
    return ['eq', a.name]
  },
  timeoutMs: 60000,
})

const textTool = cliTool({
  name: 'pixelbar_text',
  description:
    '把文字**自己渲染成点阵**再上屏（不走设备内置字体），支持中文与多行。' +
    '中文最小可读 12px、舒适 16px，**每屏最多 2 行**（256×32 屏的硬限制）。',
  parameters: {
    type: 'object',
    additionalProperties: false,
    required: ['lines'],
    properties: {
      lines: { type: 'array', items: { type: 'string' }, description: '每行一条，最多 2 行' },
      cjk: bool('按中文渲染（宋体）。不填则用 ASCII 5×7 点阵'),
      size: int('中文字号，默认 16'),
      scale: int('ASCII 放大倍数，1 或 2（默认 2）'),
      category: int('写到哪个类别，默认 2'),
      preview: str('预览图输出路径'),
      dry: bool('只编码不推送'),
    },
  },
  argv: (a) => {
    if (!Array.isArray(a.lines) || !a.lines.length) throw new Error('lines 至少要有一行')
    const v = ['text-bitmap', ...a.lines.map(String)]
    on(v, '--cjk', a.cjk)
    push(v, '--size', a.size)
    push(v, '--scale', a.scale)
    push(v, '--category', a.category)
    push(v, '--preview', a.preview)
    on(v, '--dry', a.dry)
    return v
  },
})

export const TOOLS = [
  doctorTool,
  statusTool,
  showTool,
  animTool,
  makeTool,
  sheetTool,
  facesTool,
  eqTool,
  textTool,
]

export function apply(ctx) {
  for (const tool of TOOLS) ctx.tools.register(tool)
}
