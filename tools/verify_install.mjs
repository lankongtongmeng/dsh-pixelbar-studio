// 验证**装进 profile 的那一份**能独立工作（相对路径解析对不对）。
// 装好的副本会从自己的目录找 pixelbar.py / gifs/oga / wiretest，路径算错这里就会炸。
//
// 用法：node tools/verify_install.mjs [profile目录]
import { existsSync } from 'node:fs'
import { homedir } from 'node:os'
import { join, resolve } from 'node:path'

const profile = resolve(
  process.argv[2] || process.env.DSH_PROFILE_DIR || join(homedir(), '.dsh', 'profiles', 'desktop'),
)
const entry = join(profile, 'node_modules', 'dsh-pixelbar-studio', 'lib', 'index.js')

if (!existsSync(entry)) {
  console.error(`没找到已安装的插件入口：${entry}`)
  process.exit(1)
}
console.log(`入口：${entry}`)

const m = await import(`file://${entry.replace(/\\/g, '/')}`)
console.log(`cordis name : ${m.name}`)
console.log(`inject      : ${JSON.stringify(m.inject)}`)
console.log(`工具数      : ${m.TOOLS.length}`)
console.log(`工具名      : ${m.TOOLS.map((t) => t.name).join(', ')}`)

const byName = Object.fromEntries(m.TOOLS.map((t) => [t.name, t]))
let fail = 0
for (const [tool, args] of [['pixelbar_doctor', { offline: true }], ['pixelbar_anim', { action: 'list' }]]) {
  try {
    const r = await byName[tool].execute(args)
    const first = String(r?.text || '').split('\n').filter(Boolean)[0] || ''
    console.log(`[OK ] ${tool} -> ${first.slice(0, 70)}`)
  } catch (e) {
    console.log(`[FAIL] ${tool}: ${e.message}`)
    fail += 1
  }
}
console.log(fail ? `\n安装验证：${fail} 项失败` : '\n安装验证：通过（装好的这一份能独立工作）')
process.exit(fail ? 1 : 0)
