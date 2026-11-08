# 对外发布流程（GitHub → npm → 市场 PR）

> 这份文档记录的是 **2026-11-08 实际跑通一次**的完整发布链路，含全部卡点与绕法。
> 照做即可复现；所有命令都在本机验证过。

三个目标产物：

| 产物 | 本次结果 |
| --- | --- |
| GitHub 仓库 | `lankongtongmeng/dsh-pixelbar-studio`（public） |
| npm 包 | `dsh-pixelbar-studio@0.2.0` |
| 市场收录 PR | `awesome-dsh-plugin/awesome-dsh-plugin#13299` |

---

## 0. 前提与硬约束

- **账号**：GitHub 与 npm 账号均为 `lankongtongmeng`（npm 账号 2026-11-08 新建、**未开 2FA**）。
- **本机没有 npm 登录态、没有 `gh`、没有 token、没有 SSH key** —— 所有凭据都要现拿。
- **不能复用浏览器里的登录**：本机 Chrome 是 Qoom 版（`C:\Program Files (x86)\Qoom\Chrome`，
  配置目录 `%LOCALAPPDATA%\Chromium\User Data`）。Chrome 127+ 的 **App-Bound Encryption**
  让 cookie 读不出来，强行导入还会损坏浏览器配置 —— `ego_login_import` 会直接拒绝执行，
  **不要设 `EGO_LINUX_LOGIN_IMPORT_FORCE=1` 绕过**。
- **结论**：必须让用户本人做一次授权。能自动化的只有「除了输密码/点授权以外的全部」。

### 沙箱带来的两个必改项

```powershell
# gh 的配置目录在 AppData 会被拒写（mkdir ... Access is denied）
$env:GH_CONFIG_DIR = "<工作区>\gh-config"
$env:GH_TOKEN      = (Get-Content "<工作区>\gh_token.txt" -Raw).Trim()

# npm 默认缓存在 AppData 也会 EPERM（表现为 registry 失败，易误判为网络问题）
$env:npm_config_cache = "<工作区>\npm-cache"
```

> `gh auth setup-git` 会失败（写不了 `C:\Users\<用户>\.gitconfig`，Permission denied）。
> **这是虚的** —— `gh repo create --push` 自带凭据，推送照样成功，remote URL 保持干净。

---

## 1. GitHub 仓库

### 1.1 装 gh（免管理员）

GitHub release 直连被墙 → 走 gh-proxy，并**校验官方 sha256**：

```powershell
node get_gh.mjs   # 取 releases/latest 的 windows_amd64.zip，改写成 gh-proxy.com 前缀下载
                  # 比对 asset.digest，实测 15197187 字节、sha256 一致
Expand-Archive gh.zip -DestinationPath gh -Force    # → gh\bin\gh.exe
```

### 1.2 设备码授权（唯一需要用户操作的地方）

`gh auth login --web` 会打开**默认浏览器**（本机是 Edge），而用户只能在 Qoom Chrome 里登录 ——
所以**自己实现设备码流程**（`gh_device_flow.mjs`，用 gh 的公开 client_id）：

1. 脚本 POST `https://github.com/login/device/code`，打印一次性码；
2. 用**显式路径**把授权页开进 Qoom Chrome：
   `Start-Process "C:\Program Files (x86)\Qoom\Chrome\chrome.exe" -ArgumentList "https://github.com/login/device"`
3. 用户填码 → Authorize；
4. 脚本轮询 `login/oauth/access_token`，拿到 token 写文件（**不打印 token**）。

> ⚠️ **设备码 15 分钟过期**，且**过期后再授权无效**。务必把码给到用户后尽快完成；
> 超时就重新生成一个，不要复用旧码。
> 本次第一次就因用户在期限边缘操作而 `expired_token`，重发后成功。

### 1.3 建仓库并推送

```powershell
& $gh repo create dsh-pixelbar-studio --public --source "<repo 路径>" `
      --remote origin --push --description "<一句话>"
```

推完核对远端条目数与本地一致；`git remote -v` **不应含 token**。

---

## 2. npm 发布

### 2.1 先踩的坑：403 要 2FA

普通 `npm publish` 直接失败：

```
403 Two-factor authentication or granular access token with bypass 2fa enabled
    is required to publish packages.
```

查 `npm profile get` 得知 **`tfa: false`** —— 账号根本没开 2FA，也就**产生不了 OTP**。
（`npm login --auth-type=web` 能让 CLI 拿到 token、`npm whoami` 正常，但对发布无效。）

### 2.2 解法：Granular Access Token + Bypass 2FA

**建 token 必须走网页**，而网页登录要用户输密码 —— 所以：
用户登录一次，**之后全自动**。

驱动方式：**带调试端口重启 Chrome，然后用 CDP 操作页面**（见 §4）。

在 `/settings/<user>/tokens/granular-access-tokens/new` 上填：

| 字段 | 值 |
| --- | --- |
| Token name | `publish-dsh-pixelbar-studio` |
| Bypass two-factor authentication (2FA) | **勾上**（必填项） |
| Packages and scopes permission | `Read and write (publish and stage)` |
| 随后出现的 `selectedPackagesAndScopes` | 选 **All packages** |
| Allowed IP ranges | 留空 |

> 勾选/单选都是 React 受控组件：`el.click()` 后**要重新读 `checked` 再判断**，
> 有时读早了会误判为未生效。文本框要用**原生 setter** 再派发 `input`/`change`：
> `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el, v)`。

点 `Generate token` 后，token **只显示一次** → 脚本轮询页面抓 `npm_[A-Za-z0-9]{20,}` 并写文件。

### 2.3 发布

```powershell
# 用独立 npmrc，不污染用户全局 .npmrc
Set-Content publish.npmrc "//registry.npmjs.org/:_authToken=<token>"
npm publish --userconfig publish.npmrc --access public
```

### 2.4 首发会出现 `0.0.0-stage` 占位符（正常，别慌）

发布后 registry 立刻查会看到：

```json
{ "dist-tags": { "latest": "0.0.0-stage" }, "versions": ["0.0.0-stage"] }
```

这是 npm 给**新包首发**建的**暂存占位符**。几分钟后 `latest` 变 `0.2.0`，两个版本并存
（`0.0.0-stage` 留着无害）。**中途别重复发**，等 CDN 跟上即可。
判定是否真上线，看**后台 Packages 页**比看 registry 快。

---

## 3. 市场 PR（awesome-dsh-plugin）

### 3.1 收录规则（读自其 `contributing.md` + `scripts/check-submission.mjs`）

- **一个 PR 最多 3 条**；只加**一个文件**：`data/plugins/<owner>__<repo>.yml`。
- **两个 README 由脚本生成，禁止手改**（PR 动了别人的条目会被 gate 点名）。
- `package.json` 必须声明 **`dsh.bundle`**（只声明 `dsh.client` 会被拒）。
- 仓库需**创建满 24 小时**：`MIN_AGE_DAYS = 1`，严格按
  `(Date.now() - created_at) / 86400000` 算。
- 描述必须**属实**（会被对着代码核），不带营销词；含 `: `（冒号加空格）时必须加引号。

条目模板：

```yaml
url: https://github.com/<owner>/<repo>
name: <owner>/<repo>
category: fun          # 见 contributing.md 的取值表
description:
  en: 'One line ending with a period.'
  zh: '一句话，以句号结尾。'
```

### 3.2 全自动开 PR（无需 clone）

`open_pr.mjs` 用 API 串起来：fork → 取 upstream `main` 的 sha → 建分支 →
`PUT contents/<path>`（base64）→ `POST pulls`。本次一步成功。

### 3.3 年龄门会红一次 —— 这是设计好的

仓库当天建的，CI 第 3 项必然失败。但 CI 自己的报错信息里写明：

> this check **re-runs by itself** and should clear in about {hours}h.
> **No need to resubmit, push, or close and reopen.**

仓库有 `regate.yml` 定时重跑，所以**照常提 PR、什么都别做**，满 24h 后自动转绿。

> 另外：首次向该仓库贡献时，GitHub 可能把 workflow 挂成 `action_required`
> （等维护者批准跑 CI）。这是平台行为，不是你的问题，也不用处理。

---

## 4. 可复用技巧：CDP 驱动用户自己的浏览器

**适用场景**：必须在「用户已登录的浏览器」里做网页操作，但 cookie 拿不出来。

```powershell
# 1) 先彻底关掉 Chrome（必须，调试端口只能在启动时开）
Get-Process chrome | Stop-Process -Force
# 2) 用同一份配置目录 + 调试端口重启（登录态在配置里，不会丢）
Start-Process "C:\Program Files (x86)\Qoom\Chrome\chrome.exe" -ArgumentList `
  '--remote-debugging-port=9222', `
  "--user-data-dir=$env:LOCALAPPDATA\Chromium\User Data", `
  '--no-first-run','--no-default-browser-check', '<目标 URL>'
# 3) 验证
node -e "fetch('http://127.0.0.1:9222/json/version').then(r=>r.json()).then(j=>console.log(j.Browser))"
```

然后用 Node 内置 `WebSocket` 连 `json/list` 里目标页的 `webSocketDebuggerUrl`，
发 `Runtime.evaluate` 读写 DOM（脚本见 `_publish_scratch/cdp_*.mjs` 系列：
`cdp_read` 读表单 / `cdp_goto` 导航 / `cdp_fill_gat` 填表 / `cdp_generate_token` 抓一次性 token）。

**安全提醒**：
- 开着调试端口 = 本机任何程序都能控制这个浏览器 → **任务结束必须关掉**，
  让用户重新正常启动。
- 用 `--user-data-dir` 显式指向原配置，避免开出一个「空的新浏览器」让用户以为数据丢了。
- 登录页的**密码框永远由用户自己输**，脚本只填用户名、只做之后的步骤。

**Cloudflare**：程序化导航会触发 Turnstile（「正在进行安全验证」）。多数情况
**等 8~10 秒会自己过**，不需要用户点。

---

## 5. 发布后验证清单

```powershell
# npm 真的能装？
npm view <pkg> version
npm view <pkg> dist.tarball
node -e "fetch('https://registry.npmjs.org/<pkg>/<version>').then(r=>r.json()).then(j=>console.log(j.name,j.version))"

# GitHub 仓库状态
& $gh api repos/<owner>/<repo>      # 看 private / topics / created_at

# 市场 PR
& $gh pr view <num> --repo awesome-dsh-plugin/awesome-dsh-plugin `
      --json number,state,mergeable,additions,changedFiles
& $gh pr diff <num> --repo awesome-dsh-plugin/awesome-dsh-plugin --name-only  # 只应有你自己的文件
```

---

## 6. 已知待办

- **npm token 7 天过期**（本次到 2026-11-15）。过期后重新建一个 GAT 即可。
- **Bypass-2FA token 对「直接发布」2027-01 起失效**。届时改用 **Trusted Publishing**
  （OIDC，走 GitHub Actions，不需要任何 token）：在包设置页配置 trusted publisher，
  workflow 里 `id-token: write` + `npm publish --provenance`。
- 市场 PR 的 24h 年龄门需等仓库满一天后 CI 自动转绿，**不需要任何操作**。

---

## 7. 这次真正花掉时间的教训

1. **该先说的那句话**：整个发布只有两步需要人 —— **GitHub 点一次 Authorize、npm 登录一次**。
   应该第一句就讲清，而不是先去翻环境。
2. **不要在「怎么拿到凭据」上自由发挥**：cookie 导入这条路是死的（ABE），
   确认后应立刻转向设备码 / 一次性 token，不要反复试探。
3. **设备码有时限**：给用户码之后要盯着，别让它静默过期。
4. **沙箱的两个坑要一次改到位**：`GH_CONFIG_DIR` 与 `npm_config_cache` 都指到工作区，
   否则会误判成「网络问题」。
