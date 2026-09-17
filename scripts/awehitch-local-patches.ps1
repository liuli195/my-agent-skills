<#
.SYNOPSIS
  awehitch 本地改动的**自检 + 按需补齐**（幂等，可随时重跑）。

.DESCRIPTION
  本机为了让 awehitch 正常工作做了三处本地补丁，外加一处配置调整。这些改动会在
  `npm update -g awehitch` 之后全部丢失，而 `awehitch up` 会把配置调整又写回来。

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
$tplRepatched = $false
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
      $tplRepatched = $true
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
# 由模板重新渲染两份技能（仅在补丁 2 刚被补上时才需要）
# =========================================================================
if ($tplRepatched) {
  $tplText = ReadUtf8 $tpl
  foreach ($tg in @(
      @{ path = Join-Path $env:USERPROFILE ".claude\skills\awehitch\SKILL.md"; harness = "Claude Code" },
      @{ path = Join-Path $env:USERPROFILE ".codex\skills\awehitch\SKILL.md";  harness = "Codex" }
    )) {
    $dir = Split-Path $tg.path -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    # 连接器名用占位符：真实名字每个工作区不同，由技能内说明引导 Agent 现取
    WriteUtf8 $tg.path ($tplText.Replace("{{HARNESS}}", $tg.harness).Replace("{{CONNECTOR_NAME}}", "awehitch · <本工作区>"))
  }
  Add-Row "技能重渲染" "因补丁 2" "**已重渲染**" "两份技能已按新模板重写（连接器名用占位符）"
}

# =========================================================================
# 配置调整（不是补丁）：清掉 Codex 用户级配置里的 awehitch 条目
#   每个工作区各有项目级配置；用户级条目只可能指向某一个工作区，在别处会指错。
# =========================================================================
$codexCfg = Join-Path $env:USERPROFILE ".codex\config.toml"
if (Test-Path $codexCfg) {
  $t = ReadUtf8 $codexCfg
  $block = [regex]::Match($t, '(?ms)^\[mcp_servers\.awehitch\]\r?\n.*?(?=^\[|\z)')
  if ($block.Success) {
    WriteUtf8 $codexCfg $t.Remove($block.Index, $block.Length)
    Add-Row "配置 用户级条目" "存在即清理" "**已移除**" "Codex 用户级配置里的 awehitch 条目（项目级配置接管）"
  } else {
    Add-Row "配置 用户级条目" "本来就干净" "跳过" "Codex 用户级配置里没有 awehitch 条目"
  }
} else {
  Add-Row "配置 用户级条目" "找不到文件" "未动" "没有 ~/.codex/config.toml"
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
