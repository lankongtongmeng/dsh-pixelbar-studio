// 把本插件装进 DSH profile（不跑 npm install，避免动到 profile 的依赖树）。
//
// 为什么不用 `npm install <本地目录>`：那会让 npm 重新解析整个 profile 的依赖树，
// 可能顺手改掉/剪掉别人的包。这里只做两件事——复制文件 + 往 dsh.profile.bundles 里加一行。
//
// 用法：
//   node tools/install_to_dsh.mjs                 # 装到 %USERPROFILE%\.dsh\profiles\desktop
//   node tools/install_to_dsh.mjs --profile <目录>
//   node tools/install_to_dsh.mjs --dry           # 只看会做什么
//   node tools/install_to_dsh.mjs --uninstall     # 回滚（删目录 + 去掉那一行）
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync, copyFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const PKG = 'dsh-pixelbar-studio'
const HERE = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const argv = process.argv.slice(2)
const dry = argv.includes('--dry')
const uninstall = argv.includes('--uninstall')
const pi = argv.indexOf('--profile')
const profile = resolve(
  pi >= 0 && argv[pi + 1]
    ? argv[pi + 1]
    : process.env.DSH_PROFILE_DIR || join(homedir(), '.dsh', 'profiles', 'desktop'),
)

// npm 包里会带的东西（和 package.json 的 files 保持一致）
const ITEMS = [
  'lib', 'pixelbar', 'docs',
  'pixelbar.py', 'pyproject.toml', 'run.cmd', 'cordis.patch.yml',
  'README.md', 'NOTICE.md', 'LICENSE', 'package.json',
]
const ASSETS = [
  ['gifs/oga/Pepper_publish..png', 'gifs/oga/Pepper_publish..png'],
  ['gifs/oga/carrot..png', 'gifs/oga/carrot..png'],
  ['gifs/oga/coriander_publish..png', 'gifs/oga/coriander_publish..png'],
  ['gifs/oga/saffron_publish..png', 'gifs/oga/saffron_publish..png'],
  ['gifs/oga/shichimi_publish..png', 'gifs/oga/shichimi_publish..png'],
  ['wiretest/captures.json', 'wiretest/captures.json'],
]

const dest = join(profile, 'node_modules', PKG)
const pkgJson = join(profile, 'package.json')

console.log(`插件源目录 : ${HERE}`)
console.log(`目标 profile: ${profile}`)
console.log(`安装位置   : ${dest}`)
if (dry) console.log('（--dry：只报告，不写入）')

if (!existsSync(pkgJson)) {
  console.error(`\n找不到 profile 的 package.json：${pkgJson}`)
  console.error('用 --profile <目录> 指定，或设 DSH_PROFILE_DIR 环境变量。')
  process.exit(1)
}

const raw = readFileSync(pkgJson, 'utf8')
let j
try {
  j = JSON.parse(raw)
} catch (e) {
  console.error(`profile 的 package.json 不是合法 JSON：${e.message}`)
  process.exit(1)
}
if (!Array.isArray(j.dsh?.profile?.bundles)) {
  console.error('profile 的 package.json 里没有 dsh.profile.bundles 数组。')
  process.exit(1)
}
const bundles = j.dsh.profile.bundles
const listed = bundles.includes(PKG)

if (uninstall) {
  if (!dry) {
    if (existsSync(dest)) rmSync(dest, { recursive: true, force: true })
    if (listed) {
      copyFileSync(pkgJson, `${pkgJson}.bak-before-pixelbar`)
      j.dsh.profile.bundles = bundles.filter((b) => b !== PKG)
      writeFileSync(pkgJson, `${JSON.stringify(j, null, 2)}\n`, 'utf8')
    }
  }
  console.log(`\n已回滚：删掉 ${dest}${listed ? '，并从 bundles 移除' : ''}。重启 DSH 生效。`)
  process.exit(0)
}

if (dry) {
  console.log(`\n会复制 ${ITEMS.length} 个条目 + ${ASSETS.length} 个素材文件`)
  console.log(`会往 bundles ${listed ? '（已在，跳过）' : '追加一行'}`)
  process.exit(0)
}

// 1) 复制文件
if (existsSync(dest)) rmSync(dest, { recursive: true, force: true })
mkdirSync(dest, { recursive: true })
for (const item of ITEMS) {
  const s = join(HERE, item)
  if (!existsSync(s)) { console.warn(`  [跳过] 源里没有 ${item}`); continue }
  cpSync(s, join(dest, item), { recursive: true })
}
for (const [from, to] of ASSETS) {
  const s = join(HERE, from)
  if (!existsSync(s)) { console.warn(`  [跳过] 源里没有 ${from}`); continue }
  const t = join(dest, to)
  mkdirSync(dirname(t), { recursive: true })
  copyFileSync(s, t)
}
// 别把 __pycache__ 带过去
rmSync(join(dest, 'pixelbar', '__pycache__'), { recursive: true, force: true })

// 2) 注册进 bundles
if (listed) {
  console.log('\nbundles 里已经有它，跳过注册。')
} else {
  copyFileSync(pkgJson, `${pkgJson}.bak-before-pixelbar`)
  j.dsh.profile.bundles = [...bundles, PKG]
  writeFileSync(pkgJson, `${JSON.stringify(j, null, 2)}\n`, 'utf8')
  console.log(`\nbundles 已追加 "${PKG}"（原文件备份为 package.json.bak-before-pixelbar）`)
}

console.log('\n装好了。接下来：')
console.log('  1. 重启 DSH')
console.log('  2. 新会话里说「看看 PixelBar 状态」，模型会调用 pixelbar_status')
console.log('\n回滚：node tools/install_to_dsh.mjs --uninstall')
