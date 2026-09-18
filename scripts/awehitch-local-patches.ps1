<#
.SYNOPSIS
  awehitch 本地改动的**自检 + 按需补齐**（幂等，可随时重跑）。

.DESCRIPTION
  本机为了让 awehitch 正常工作做了**六处**本地补丁，外加一处历史遗留清理。
  这些改动会在 `npm update -g awehitch` 之后全部丢失。

  补丁 4 之后，`awehitch up` 不再往 Codex 用户级配置写条目了，所以那处清理只对
  存量有效（补丁 4 上之前留下的条目）；新写入不会再产生，也就不会再写坏。

  **本脚本不会盲目补丁。** 它对每一处先做自检，判断"这个缺陷现在还在不在"：

    已打          → 跳过
    上游已修复    → **不打**，只报告（避免往已经修好的代码里塞改动）
    判不准        → **不打**，报告出来交给人工确认
    确认仍存在    → 补上

  自检是**静态启发式**（读代码找特征），不是运行时验证。所以它只回答"代码里看起来
  有没有处理这件事"。判不准时一律选择不动手。

  什么时候跑：
  - `npm update -g awehitch` 之后
  - `awehitch up -w <仓库>` 之后（它会往 Codex 用户级配置写回一条条目）
  - 怀疑哪里不对时

  背景与每处改动的详细说明见 docs/research/chatgpt-collaboration-setup.md 第 5.3 / 5.4 节。
#>
$ErrorActionPreference = "Stop"

$awehitchRoot = Join-Path $env:APPDATA "npm\node_modules\awehitch"
$rows = [System.Collections.Generic.List[object]]::new()

function Add-Row($name, $verdict, $action, $detail) {
  $rows.Add([pscustomobject]@{ 项 = $name; 自检 = $verdict; 动作 = $action; 说明 = $detail })
}
function ReadUtf8($p) { [System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8) }
function WriteUtf8($p, $t) { [System.IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($false))) }

if (-not (Test-Path $awehitchRoot)) {
  Write-Host "找不到 awehitch 安装目录：$awehitchRoot" -ForegroundColor Red
  exit 1
}
$ver = "未知"
try { $ver = (Get-Content (Join-Path $awehitchRoot "package.json") -Raw | ConvertFrom-Json).version } catch {}

Write-Host "awehitch 本地改动自检" -ForegroundColor Cyan
Write-Host "安装目录：$awehitchRoot"
Write-Host "版本：$ver`n"

# =========================================================================
# 补丁 1：浏览器启动参数
#   缺陷：本机 Chrome 在 ChatGPT 页面上 devicePixelRatio 异常（0.909 / 视口宽 1.1 倍），
#         Playwright 的每次点击都被判定为"被其他元素遮挡"，输入框与表单全点不动。
#   修法：给启动参数加 --force-device-scale-factor=1。
#   自检：代码里是否已经强制了缩放因子。这是环境问题，除了强制缩放没有别的修法，
#         所以"代码里有这个处理"就等价于"缺陷已被处理"。
# =========================================================================
$browserJs = Join-Path $awehitchRoot "dist\control-plane\browser.js"
if (-not (Test-Path $browserJs)) {
  Add-Row "补丁 1 启动参数" "找不到文件" "未动" "缺 browser.js，awehitch 结构可能变了"
} else {
  $t = ReadUtf8 $browserJs
  if ($t -match "--force-device-scale-factor") {
    Add-Row "补丁 1 启动参数" "已打" "跳过" "启动参数里已有 force-device-scale-factor"
  } elseif ($t -match "deviceScaleFactor|force-device-scale|devicePixelRatio") {
    Add-Row "补丁 1 启动参数" "上游已处理" "**未打**" "代码里已有缩放/像素比相关处理，先不动——请人工确认是否等价"
  } else {
    $old = 'args: ["--disable-blink-features=AutomationControlled"],'
    if ($t.Contains($old)) {
      if (-not (Test-Path "$browserJs.orig")) { Copy-Item $browserJs "$browserJs.orig" -Force }
      WriteUtf8 $browserJs $t.Replace($old, 'args: ["--disable-blink-features=AutomationControlled", "--force-device-scale-factor=1"],')
      Add-Row "补丁 1 启动参数" "缺陷仍在" "**已补上**" "无缩放处理 + 锚点匹配 → 补丁已应用"
    } else {
      Add-Row "补丁 1 启动参数" "判不准" "**未打**" "没有缩放处理，但也找不到插入锚点——awehitch 可能改版，需人工处理"
    }
  }
}

# =========================================================================
# 补丁 2：技能模板的多工作区说明
#   缺陷：模板把连接器名写死渲染进技能；同一账号有多个连接器时，技能里的名字在别的
#         工作区就是错的。（dist/adapters/codex.js 每次 up 都会重写技能，所以只能改模板。）
#   自检：模板里是否已经有"按工作区取连接器名"的引导（找 connectorName 查询或等价措辞）。
# =========================================================================
$tpl = Join-Path $awehitchRoot "skill\SKILL.md.template"
$noteText = @'

**连接器名（重要）** — 每个工作区在 ChatGPT 里各有**一个专属连接器**，同一账号里可能
同时存在多个 awehitch 连接器。**务必只用本工作区的那一个。**
这份技能里渲染进去的名字，属于"生成它时"的那个工作区；**若你当前不在那个工作区，
先取准确名字**：

    awehitch doctor -w <workspace> --json      →  读其中的 `connectorName`

然后把下文出现的连接器名一律替换成该值。
'@
if (-not (Test-Path $tpl)) {
  Add-Row "补丁 2 技能模板" "找不到文件" "未动" "缺 SKILL.md.template"
} else {
  $t = ReadUtf8 $tpl
  if ($t.Contains("连接器名（重要）")) {
    Add-Row "补丁 2 技能模板" "已打" "跳过" "模板里已有本工作区连接器说明"
  } elseif ($t -match "connectorName|per.workspace|每个工作区|one connector per") {
    Add-Row "补丁 2 技能模板" "上游已处理" "**未打**" "模板里已出现按工作区区分连接器的措辞，先不动——请人工确认"
  } else {
    $anchor = "ChatGPT thinks. {{HARNESS}} works."
    if ($t.Contains($anchor)) {
      if (-not (Test-Path "$tpl.orig")) { Copy-Item $tpl "$tpl.orig" -Force }
      WriteUtf8 $tpl $t.Replace($anchor, $anchor + $noteText)
      Add-Row "补丁 2 技能模板" "缺陷仍在" "**已补上**" "锚点匹配 → 说明已插入"
    } else {
      Add-Row "补丁 2 技能模板" "判不准" "**未打**" "找不到插入锚点——模板可能改版，需人工处理"
    }
  }
}

# =========================================================================
# 补丁 3：读回比对剔除「展开」按钮文字
#   缺陷：消息长到被折叠时，ChatGPT 把「展开」按钮文字混进 innerText，读回比对必然
#         失败并抛 SEND_FAILED——而消息其实完整送达。
#   修法：normalizeForCompare() 里剔除末尾的「展开 / 收起 / Show more / Show less」。
#   自检：读回比对那条链路上是否已经处理了折叠标签。
# =========================================================================
$composerJs = Join-Path $awehitchRoot "dist\control-plane\composer.js"
# 插入内容：注释（含 PATCH(local) 标记，供下次自检识别）+ 剔除规则。
# 注意：锚点与特征串一律只用 ASCII——同样的中日文字符在本脚本里和被改文件里，
# 可能一个存成字面量、一个存成 \uXXXX 转义序列，直接比对会失败。
$appliedMarker = 'PATCH(local)'
$stripBlock = '        // PATCH(local): strip the folded-message "expand" toggle label.' + "`n" +
              '        // Without it the readback always mismatches and throws SEND_FAILED' + "`n" +
              '        // even though the message arrived intact (measured: folds from ~16 lines).' + "`n" +
              '        .replace(/\s*(展开|收起|Show more|Show less)\s*$/i, "")'
# 锚点：连同行首缩进一起匹配，这样插入块的缩进才对得上。
$chainAnchor = '        .replace(/\s+/g, " ")'
if (-not (Test-Path $composerJs)) {
  Add-Row "补丁 3 读回比对" "找不到文件" "未动" "缺 composer.js"
} else {
  $t = ReadUtf8 $composerJs
  if ($t.Contains($appliedMarker)) {
    Add-Row "补丁 3 读回比对" "已打" "跳过" "文件里有本补丁的 PATCH(local) 标记"
  } elseif ($t -match "Show more|Show less|收起") {
    # 精确特征：真正修了这个缺陷，代码里必然要提到折叠按钮的文案。
    # 不要用 collapse / 折叠 这类泛词——上游原版注释里就有一句无关的 "it collapses the blank lines"。
    Add-Row "补丁 3 读回比对" "上游已处理" "**未打**" "代码里已提到折叠按钮文案，疑似已修——先不动，请人工确认"
  } else {
    $n = ([regex]::Matches($t, [regex]::Escape($chainAnchor))).Count
    if ($n -eq 1) {
      if (-not (Test-Path "$composerJs.orig")) { Copy-Item $composerJs "$composerJs.orig" -Force }
      WriteUtf8 $composerJs $t.Replace($chainAnchor, $stripBlock + "`n" + $chainAnchor)
      Add-Row "补丁 3 读回比对" "缺陷仍在" "**已补上**" "锚点唯一命中 → 剔除规则已插入"
    } elseif ($n -gt 1) {
      Add-Row "补丁 3 读回比对" "判不准" "**未打**" "锚点在文件里出现 $n 次，不唯一——需人工处理"
    } else {
      Add-Row "补丁 3 读回比对" "判不准" "**未打**" "找不到插入锚点——比对函数可能已重写，需人工处理"
    }
  }
}

# =========================================================================
# 补丁 4：别再往 Codex 用户级配置写条目 —— 那个写入每次都会写坏配置
#   缺陷：`setupCodexAdapter`（dist/adapters/codex.js）每次 up 都往用户级
#         ~/.codex/config.toml 写 awehitch 条目。它覆盖**旧格式**条目时（旧格式自带
#         [mcp_servers.awehitch.env] 子表）会同时踩两层：
#           ① 替换用的 body 结尾没有换行 → 与遗留的子表头粘成一行
#           ② 遗留的子表与新格式的内联表 env = { ... } 冲突（TOML 重复定义）
#         两层叠加 → 配置无效 → Codex 起不来（failed to load bootstrap configuration）。
#         根子在 findTableToml：它把**任何** [xxx] 表头都当块边界，认不出子表是自己的。
#   修法：① 用户级条目干脆不写（设计上每个工作区各有项目级配置，用户级条目只可能指错）
#         ② codexAdapterStatus 也接受项目级配置，免得 doctor 误报「未接入」
#         ③ doctor 调用处把 workspace 传进去（② 靠它拿项目路径）
#   自检：codex.js 里有没有本补丁的 PATCH(local) 标记
# =========================================================================
$codexJs = Join-Path $awehitchRoot "dist\adapters\codex.js"
$cliJs = Join-Path $awehitchRoot "dist\cli\index.js"
$p4Marker = 'PATCH(local): never write the user-level Codex entry'
# 一律用**单行**锚点：多行锚点会踩行尾差异（同样内容可能一处 LF、一处 CRLF）
$aWrite = '    const next = upsertCodexMcpEntry(previous, opts.cliEntry, opts.workspaceRoot);'
$aSig = 'export function codexAdapterStatus() {'
$aRet = '    return { skillInstalled: fs.existsSync(skillPath), mcpRegistered, sandboxAllowed, configPath };'
$aCall = '            const status = impl.status();'

if (-not (Test-Path $codexJs) -or -not (Test-Path $cliJs)) {
  Add-Row "补丁 4 不写用户级配置" "找不到文件" "未动" "缺 codex.js 或 cli/index.js"
} else {
  $cx = ReadUtf8 $codexJs
  $cl = ReadUtf8 $cliJs
  if ($cx.Contains($p4Marker)) {
    Add-Row "补丁 4 不写用户级配置" "已打" "跳过" "codex.js 里有本补丁的 PATCH(local) 标记"
  } elseif ((([regex]::Matches($cx, [regex]::Escape($aWrite))).Count -eq 1) -and
            (([regex]::Matches($cx, [regex]::Escape($aSig))).Count -eq 1) -and
            (([regex]::Matches($cx, [regex]::Escape($aRet))).Count -eq 1) -and
            (([regex]::Matches($cl, [regex]::Escape($aCall))).Count -eq 1)) {
    # ① 不写用户级条目：让 next === previous，后面那个 if 就永远不会落盘
    $cx = $cx.Replace($aWrite, '    const next = previous; // ' + $p4Marker + ' (docs/research/chatgpt-collaboration-setup.md)')
    # ② 状态检查也认项目级配置
    $cx = $cx.Replace($aSig, 'export function codexAdapterStatus(workspace) { // ' + $p4Marker)
    $projCheck = @'
    // PATCH(local): the entry lives in each workspace's project-level .codex/config.toml
    // now; the user-level entry is never written any more.
    if (!mcpRegistered && workspace && workspace.root) {
        try {
            const projectConfig = fs.readFileSync(path.join(workspace.root, ".codex", "config.toml"), "utf8");
            mcpRegistered = /\[mcp_servers\.awehitch\]/.test(projectConfig);
        }
        catch {
            // no project-level config for this workspace
        }
    }
'@
    # 行尾规范化：本脚本被 .gitattributes 定为 CRLF，而被改文件是 LF。
    # 不规范化的话，全新检出后会把 CRLF 行插进 LF 文件（功能无害但不干净、不确定）。
    $projCheck = ($projCheck -replace "`r`n", "`n").TrimEnd()
    $cx = $cx.Replace($aRet, $projCheck + "`n" + $aRet)
    # ③ doctor 调用处把 workspace 传进去（② 靠它拿项目路径）
    $cl = $cl.Replace($aCall, '            const status = impl.status(workspace); // ' + $p4Marker)
    foreach ($f in @(
        @{ p = $codexJs; t = $cx },
        @{ p = $cliJs;   t = $cl }
      )) {
      if (-not (Test-Path "$($f.p).orig")) { Copy-Item $f.p "$($f.p).orig" -Force }
      WriteUtf8 $f.p $f.t
    }
    Add-Row "补丁 4 不写用户级配置" "缺陷仍在" "**已补上**" "①不写用户级条目 ②状态认项目级配置 ③doctor 传入工作区"
  } else {
    Add-Row "补丁 4 不写用户级配置" "判不准" "**未打**" "四处锚点未能全部唯一命中——awehitch 可能改版，需人工处理"
  }
}

# =========================================================================
# 补丁 5：bridge 认得出「记录已死」
#   缺陷：`findBridgeObservation`（dist/bridge/runtime.js）**先探端口、后查进程**。
#         重启之后，旧运行记录里的端口往往已被**另一个工作区**占着 —— 默认端口
#         48765 是全机共享的，被占时新实例会静默退到临时端口，而旧记录里存的很可能
#         正是那条被邻居占着的 48765。于是它判为 `workspace_mismatch`（状态不明）
#         → `ensureBridge`（dist/process/daemon.js）直接抛错拒绝启动
#         → `up` / `connector-setup` 全被挡住，只有手工挪走记录才能解。
#   修法：把「记录里的进程是否还在」提到端口探测**之前** —— 记录里的进程都不在了，
#         那份记录就是废的，那个端口现在谁用着都无所谓。
#   边界：**不修**「进程号被系统回收」那一支。修它必须把「状态不明」降级，而端口探测
#         只是一次 HTTP 试探，服务短暂卡顿就会被误判成死亡，有误杀活体服务的风险。
#   自检：runtime.js 里有没有本补丁的 PATCH(local) 标记
# =========================================================================
$runtimeJs = Join-Path $awehitchRoot "dist\bridge\runtime.js"
$p5Marker = 'PATCH(local): a dead recorded pid makes the record stale'
$aFind = @'
export async function findBridgeObservation(workspaceId) {
    const runtime = readRuntimeState(workspaceId);
    if (!runtime)
        return { state: "stopped", runtime: null, reason: "runtime_missing" };
    const health = await probeBridge(runtime.port);
    if (health && health.workspaceId === workspaceId) {
        return { state: "healthy", runtime };
    }
    if (health) {
        return { state: "unknown", runtime, reason: "workspace_mismatch" };
    }
    const pid = observePid(runtime.pid);
    if (pid === "missing")
        return { state: "stopped", runtime, reason: "pid_missing" };
    return { state: "unknown", runtime, reason: pid === "unknown" ? "pid_unknown" : "probe_failed" };
}
'@
$rFind = @'
export async function findBridgeObservation(workspaceId) {
    const runtime = readRuntimeState(workspaceId);
    if (!runtime)
        return { state: "stopped", runtime: null, reason: "runtime_missing" };
    // PATCH(local): a dead recorded pid makes the record stale — whoever answers
    // on that port is irrelevant. Check the pid BEFORE probing the port.
    const pid = observePid(runtime.pid);
    if (pid === "missing")
        return { state: "stopped", runtime, reason: "pid_missing" };
    const health = await probeBridge(runtime.port);
    if (health && health.workspaceId === workspaceId) {
        return { state: "healthy", runtime };
    }
    if (health) {
        return { state: "unknown", runtime, reason: "workspace_mismatch" };
    }
    return { state: "unknown", runtime, reason: pid === "unknown" ? "pid_unknown" : "probe_failed" };
}
'@
# 行尾规范化：本脚本被 .gitattributes 定为 CRLF，而被改文件是 LF
$aFind = ($aFind -replace "`r`n", "`n").TrimEnd()
$rFind = ($rFind -replace "`r`n", "`n").TrimEnd()

if (-not (Test-Path $runtimeJs)) {
  Add-Row "补丁 5 bridge 判断顺序" "找不到文件" "未动" "缺 bridge/runtime.js"
} else {
  $t = ReadUtf8 $runtimeJs
  if ($t.Contains($p5Marker)) {
    Add-Row "补丁 5 bridge 判断顺序" "已打" "跳过" "runtime.js 里有本补丁的 PATCH(local) 标记"
  } elseif (([regex]::Matches($t, [regex]::Escape($aFind))).Count -eq 1) {
    if (-not (Test-Path "$runtimeJs.orig")) { Copy-Item $runtimeJs "$runtimeJs.orig" -Force }
    WriteUtf8 $runtimeJs $t.Replace($aFind, $rFind)
    Add-Row "补丁 5 bridge 判断顺序" "缺陷仍在" "**已补上**" "整函数锚点唯一命中 → 判断顺序已调换"
  } else {
    Add-Row "补丁 5 bridge 判断顺序" "判不准" "**未打**" "整函数锚点未能唯一命中——awehitch 可能改版，需人工处理"
  }
}

# =========================================================================
# 补丁 6：技能模板的重新连接流程
#   缺陷：模板把重连的触发条件挂在 `chatgptSetup.needed` / `chatgptRepair.needed`
#         上。重启之后这两个标志**不会亮** —— bridge 已死，doctor 无法确认状态，
#         直接跳过整块连接器检查；而且真实链路还漏了**唯一真正重建连接**的那一步
#         （`connector-setup`）。另有 doctor 门禁（"本地不全绿就不开 ChatGPT"），
#         它既不亮也不准，实测误导。
#   修法：① 重连那一节整节替换为实测三步：试一次最小 [C2C] 往返 → 报出本工作区名
#           即已连上 → 不通则跑 `connector-setup` 再回到第一步
#         ② 同一模板里另一处引用同一套标志的地方（doctor 门禁）**同步改** ——
#            两处必须一起改，否则技能文本自相矛盾
#         ③ 登录表述更正为**异常路径**：默认全自动（浏览器配置保留登录态），
#            只有返回 needsLogin 时才需要人登录一次
#   自检：模板里有没有本补丁的 PATCH(local) 标记
# =========================================================================
$tpl6 = Join-Path $awehitchRoot "skill\SKILL.md.template"
$p6Marker = 'PATCH(local): reconnect flow'
$aGate = @'
0. `awehitch doctor -w <workspace> --json` (auto-repairs). Doctor gate: if
   local is not green, do not open ChatGPT and do not send INIT. Follow its
   `chatgptRepair` / `namedRepair` guidance first.
'@
$rGate = @'
0. `awehitch doctor -w <workspace> --json` is **diagnostics only, never a
   gate** — and never block on it. Its repair flags do not fire in the
   reconnect case, so a green doctor does not mean the connection works.
'@
$aReconnect = @'
## Workflow: reconnect after address reclaim

When doctor reports `chatgptSetup.needed` or `chatgptRepair.needed`: tell the
user its `userMessage`, then run `awehitch -w <workspace> --json`
(or `chatgptSetup.command`). It deletes THIS workspace's connector and
recreates it with the new address — it never clicks Reconnect, and never
touches another workspace's connector. Then doctor again.

If that command fails, fall back to the manual path in the first-time setup
workflow: follow `manualFallback.steps` to delete and recreate
`connectorName` with the new address. Never click Reconnect — the old
address is dead and that page hangs on "This site cannot be reached".
'@
$rReconnect = @'
## Workflow: reconnect（"重新连接" — after a reboot, or an address reclaim）

<!-- PATCH(local): reconnect flow -->

The only test that matters is **whether it works**. Never guess from doctor's
flags: after a reboot they never light up — the bridge is dead, so doctor
cannot confirm the state and skips the connector check entirely.

1. **Try one minimal round-trip.** `awehitch_open_chat` for the task, then
   `awehitch_send_state`:

```
[C2C]
STATE: CONNECT_CHECK
Use the "<connectorName>" connector: call workspace_info and read a
hello-style top-level file. Reply with the workspace name.
```

   Then `awehitch_wait_reply`.
2. **The reply names this workspace → connected.** Get on with the task.
3. **Anything else → rebuild with one command:**

   `awehitch connector-setup -w <workspace> --json`

   It ensures the bridge, ensures a tunnel, deletes this workspace's old
   connector, recreates it with the current address, and authorises it.
   **This is fully automatic** — the browser profile keeps the ChatGPT login,
   so no human step is needed. Only when it reports `needsLogin` do you ask
   the user to log in (ONE action), then re-run the same command. Then go
   back to step 1.
4. If it still fails, fall back to `manualFallback.steps` as in first-time
   setup. Never click Reconnect, and never touch another workspace's
   connector — that page hangs on "This site cannot be reached".
'@
$aGate = ($aGate -replace "`r`n", "`n").TrimEnd()
$rGate = ($rGate -replace "`r`n", "`n").TrimEnd()
$aReconnect = ($aReconnect -replace "`r`n", "`n").TrimEnd()
$rReconnect = ($rReconnect -replace "`r`n", "`n").TrimEnd()

if (-not (Test-Path $tpl6)) {
  Add-Row "补丁 6 重连流程" "找不到文件" "未动" "缺 skill/SKILL.md.template"
} else {
  $t = ReadUtf8 $tpl6
  if ($t.Contains($p6Marker)) {
    Add-Row "补丁 6 重连流程" "已打" "跳过" "模板里有本补丁的 PATCH(local) 标记"
  } elseif ((([regex]::Matches($t, [regex]::Escape($aGate))).Count -eq 1) -and
            (([regex]::Matches($t, [regex]::Escape($aReconnect))).Count -eq 1)) {
    if (-not (Test-Path "$tpl6.orig")) { Copy-Item $tpl6 "$tpl6.orig" -Force }
    $t = $t.Replace($aGate, $rGate)
    $t = $t.Replace($aReconnect, $rReconnect)
    WriteUtf8 $tpl6 $t
    Add-Row "补丁 6 重连流程" "缺陷仍在" "**已补上**" "两处锚点各唯一命中 → 重连节与 doctor 门禁已改写"
  } else {
    Add-Row "补丁 6 重连流程" "判不准" "**未打**" "两处锚点未能各唯一命中——模板可能改版，需人工处理"
  }
}

# =========================================================================
# 由模板重新渲染两份技能
#   判据是「渲染结果与磁盘上那份不一致」，**不是**「某个补丁刚被打上」——
#   后者依赖瞬时状态：该补丁已打过时走「跳过」分支，重渲染就永远不会发生
#   （实测踩过：补丁 6 改完模板，两份技能却没跟着更新）。现在这样幂等、自愈。
#   渲染时连接器名用占位符：真实名字每个工作区不同，由技能内说明引导 Agent 现取。
# =========================================================================
$tplText = ReadUtf8 $tpl
$rerendered = [System.Collections.Generic.List[string]]::new()
foreach ($tg in @(
    @{ path = Join-Path $env:USERPROFILE ".claude\skills\awehitch\SKILL.md"; harness = "Claude Code" },
    @{ path = Join-Path $env:USERPROFILE ".codex\skills\awehitch\SKILL.md";  harness = "Codex" }
  )) {
  $dir = Split-Path $tg.path -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  $rendered = $tplText.Replace("{{HARNESS}}", $tg.harness).Replace("{{CONNECTOR_NAME}}", "awehitch · <本工作区>")
  $current = if (Test-Path $tg.path) { ReadUtf8 $tg.path } else { "" }
  if ($current -ne $rendered) {
    WriteUtf8 $tg.path $rendered
    $rerendered.Add($tg.harness)
  }
}
if ($rerendered.Count -gt 0) {
  Add-Row "技能重渲染" "与模板不一致" "**已重渲染**" ("两份技能已按新模板重写：" + ($rerendered -join "、"))
} else {
  Add-Row "技能重渲染" "与模板一致" "跳过" "两份技能已经是最新模板渲染的结果"
}

# =========================================================================
# 历史遗留清理（不是补丁，补丁 4 之后已不再需要）：清掉 Codex 用户级配置里的 awehitch 条目
#   补丁 4 之后 up 不再写这条了，所以这里只用来收拾**存量**——补丁 4 上之前留下的那条，
#   以及被它写坏的粘行/遗留子表（整块删掉即可一并带走）。
#   每个工作区各有项目级配置；用户级条目只可能指向某一个工作区，在别处会指错。
# =========================================================================
$codexCfg = Join-Path $env:USERPROFILE ".codex\config.toml"
if (Test-Path $codexCfg) {
  $t = ReadUtf8 $codexCfg
  $block = [regex]::Match($t, '(?ms)^\[mcp_servers\.awehitch\]\r?\n.*?(?=^\[|\z)')
  if ($block.Success) {
    WriteUtf8 $codexCfg $t.Remove($block.Index, $block.Length)
    # 兜底自检：整块删掉之后，配置里不该再有"粘行"（一行里出现两个表头）。
    # 这正是补丁 4 要根治的那个损坏；真出现说明删除没删干净。
    $left = ReadUtf8 $codexCfg
    if ($left -match '(?m)\}[ \t]*\[') {
      Add-Row "遗留 用户级条目" "删了但仍粘行" "**已移除**" "条目已删，配置里还有粘行——需人工检查 $codexCfg"
    } else {
      Add-Row "遗留 用户级条目" "存在即清理" "**已移除**" "补丁 4 之前留下的用户级条目（项目级配置接管）"
    }
  } else {
    Add-Row "遗留 用户级条目" "本来就干净" "跳过" "没有补丁 4 之前留下的用户级条目"
  }
} else {
  Add-Row "遗留 用户级条目" "找不到文件" "未动" "没有 ~/.codex/config.toml"
}

# --- 汇总 -------------------------------------------------------------------
Write-Host ""
$rows | Format-Table -AutoSize | Out-String | Write-Host

$needHuman = $rows | Where-Object { $_.自检 -in @("上游已处理", "判不准", "找不到文件") }
$patched = $rows | Where-Object { $_.动作 -match "已补上|已重渲染|已移除" }

if ($patched.Count -gt 0) {
  Write-Host "本次改动 $($patched.Count) 项。" -ForegroundColor Yellow
}
if ($needHuman.Count -gt 0) {
  Write-Host "有 $($needHuman.Count) 项**没有动手**，需要人工确认：" -ForegroundColor Red
  foreach ($r in $needHuman) { Write-Host "  - $($r.项)：$($r.说明)" -ForegroundColor Red }
  Write-Host "  疑似上游已修复，或 awehitch 改版导致锚点失效。请对照文档 5.3 节人工判断后再决定。" -ForegroundColor Red
  exit 1
}
Write-Host "自检完成：无需人工介入。" -ForegroundColor Green
