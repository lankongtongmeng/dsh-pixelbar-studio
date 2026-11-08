// 插件冒烟测试：不装进 DSH，直接 import 插件模块，用假 ctx 收集工具并实跑几个只读/安全命令。
// 目的：验证 apply() 能注册工具、argv 拼装正确、Python 桥真的能调通。
//
// 用法：node tools/smoke_plugin.mjs
import { apply, inject, name, TOOLS } from '../lib/index.js'

const fail = []
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want)
  console.log(`${ok ? '[OK ]' : '[FAIL]'} ${label}${ok ? '' : `  got=${JSON.stringify(got)} want=${JSON.stringify(want)}`}`)
  if (!ok) fail.push(label)
}

check('导出的 cordis name', name, 'pixelbar-studio')
check('inject 含 tools', inject.includes('tools'), true)
check('工具数', TOOLS.length, 9)

// 用假 ctx 走一遍 apply，确认注册路径可用
const registered = []
apply({ tools: { register: (t) => { registered.push(t); return () => {} } } })
check('apply 注册的工具数', registered.length, TOOLS.length)

// 每个工具的形状：注册给模型的是原始 JSON Schema，这里自己挡住缺字段
for (const t of registered) {
  const bad = []
  if (!t.name || typeof t.name !== 'string') bad.push('name')
  if (!t.description) bad.push('description')
  if (!t.parameters || t.parameters.type !== 'object') bad.push('parameters')
  if (typeof t.execute !== 'function') bad.push('execute')
  if (!t.output || typeof t.output.render !== 'function') bad.push('output.render')
  if (bad.length) { console.log(`[FAIL] 工具 ${t.name || '?'} 缺: ${bad.join(', ')}`); fail.push(t.name) }
}
console.log(`[OK ] ${registered.length} 个工具形状齐备`)
console.log(`     工具名：${registered.map((t) => t.name).join(', ')}`)

// 实跑：只读 / 本地命令，不碰设备
const byName = Object.fromEntries(registered.map((t) => [t.name, t]))

async function run(toolName, args) {
  const t = byName[toolName]
  if (!t) { console.log(`[FAIL] 没有工具 ${toolName}`); fail.push(toolName); return null }
  try {
    const r = await t.execute(args)
    const text = r?.text ?? ''
    console.log(`[OK ] ${toolName}(${JSON.stringify(args)}) -> ${text.length} 字符`)
    console.log(text.split('\n').slice(0, 6).map((l) => `       ${l}`).join('\n'))
    return text
  } catch (e) {
    console.log(`[FAIL] ${toolName} 抛错：${e.message}`)
    fail.push(toolName)
    return null
  }
}

await run('pixelbar_doctor', { offline: true })
await run('pixelbar_anim', { action: 'list' })

console.log(fail.length ? `\n冒烟测试：${fail.length} 项失败 -> ${fail.join(', ')}` : '\n冒烟测试：全部通过')
process.exit(fail.length ? 1 : 0)
