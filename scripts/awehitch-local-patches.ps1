<#
.SYNOPSIS
  重放 awehitch 0.3.2 上经过真实入口验证的本地补丁。
.DESCRIPTION
  只保留在干净 0.3.2 上复现并经同一入口验证的补丁 1、3、4、7。
  旧补丁 2、5、6 没有取得失败证据，因此不再重放。
#>
$ErrorActionPreference = "Stop"
$root = Join-Path $env:APPDATA "npm\node_modules\awehitch"
$rows = [System.Collections.Generic.List[object]]::new()
function Row($name,$verdict,$action,$detail) { $rows.Add([pscustomobject]@{项=$name;自检=$verdict;动作=$action;说明=$detail}) }
function ReadUtf8($path) { [IO.File]::ReadAllText($path,[Text.Encoding]::UTF8) }
function WriteUtf8($path,$text) { [IO.File]::WriteAllText($path,$text,(New-Object Text.UTF8Encoding($false))) }
function BackupOnce($path) { if (-not (Test-Path "$path.orig")) { Copy-Item $path "$path.orig" -Force } }
if (-not (Test-Path $root)) { throw "找不到 awehitch 安装目录：$root" }
$version = (Get-Content (Join-Path $root "package.json") -Raw | ConvertFrom-Json).version
if ($version -ne "0.3.2") { throw "本脚本只验证过 awehitch 0.3.2；当前版本为 $version，拒绝修改。" }

# 补丁 1：connector-setup 实测为输入框可见且启用，但点击被父元素持续拦截。
$file = Join-Path $root "dist\control-plane\browser.js"
$anchor = 'args: ["--disable-blink-features=AutomationControlled", ...proxyLaunchArgs()],'
if (-not (Test-Path $file)) { Row "补丁 1 页面缩放" "找不到文件" "未动" "缺 browser.js" }
else {
  $text = ReadUtf8 $file
  if ($text.Contains("--force-device-scale-factor=1")) { Row "补丁 1 页面缩放" "已处理" "跳过" "启动参数已固定缩放比例" }
  elseif (([regex]::Matches($text,[regex]::Escape($anchor))).Count -eq 1) {
    BackupOnce $file
    WriteUtf8 $file $text.Replace($anchor,'args: ["--disable-blink-features=AutomationControlled", "--force-device-scale-factor=1", ...proxyLaunchArgs()],')
    Row "补丁 1 页面缩放" "缺陷仍在" "已补上" "唯一锚点命中"
  } else { Row "补丁 1 页面缩放" "判不准" "未动" "锚点不唯一或已改版" }
}

# 补丁 3：910 字节消息已完整抵达，但折叠按钮文字令读回比对误报 SEND_FAILED。
$file = Join-Path $root "dist\control-plane\composer.js"
$marker = 'PATCH(local): strip folded-message toggle labels'
$anchor = '        .replace(/\s+/g, " ")'
$replacement = '        // ' + $marker + "`n" + '        .replace(/\s*(展开|收起|Show more|Show less)\s*$/i, "")' + "`n" + $anchor
if (-not (Test-Path $file)) { Row "补丁 3 长消息读回" "找不到文件" "未动" "缺 composer.js" }
else {
  $text = ReadUtf8 $file
  if ($text.Contains($marker)) { Row "补丁 3 长消息读回" "已处理" "跳过" "已有本地补丁标记" }
  elseif (([regex]::Matches($text,[regex]::Escape($anchor))).Count -eq 1) {
    BackupOnce $file; WriteUtf8 $file $text.Replace($anchor,$replacement)
    Row "补丁 3 长消息读回" "缺陷仍在" "已补上" "唯一锚点命中"
  } else { Row "补丁 3 长消息读回" "判不准" "未动" "锚点不唯一或已改版" }
}

# 补丁 4：awehitch up 实测改写 ~/.codex/config.toml；本仓库已有项目级注册。
$codex = Join-Path $root "dist\adapters\codex.js"; $cli = Join-Path $root "dist\cli\index.js"
$marker = 'PATCH(local): keep Codex registration project-local'
$aWrite = '    const next = upsertCodexMcpEntry(previous, opts.cliEntry, opts.workspaceRoot);'
$aSig = 'export function codexAdapterStatus() {'
$aRet = '    return { skillInstalled: fs.existsSync(skillPath), mcpRegistered, sandboxAllowed, configPath };'
$aCall = '            const status = impl.status();'
if (-not (Test-Path $codex) -or -not (Test-Path $cli)) { Row "补丁 4 项目级配置" "找不到文件" "未动" "缺 Codex 适配器文件" }
else {
  $cx=ReadUtf8 $codex; $cl=ReadUtf8 $cli
  $cxDone=$cx.Contains('const next = previous; // '+$marker) -and $cx.Contains('path.join(workspace.root, ".codex", "config.toml")')
  $clDone=$cl.Contains('const status = impl.status(workspace); // '+$marker)
  if ($cxDone -and $clDone) { Row "补丁 4 项目级配置" "已处理" "跳过" "两个文件均有完整最终特征" }
  else {
    $canPatch=$true
    if (-not $cxDone -and -not ((([regex]::Matches($cx,[regex]::Escape($aWrite))).Count -eq 1) -and (([regex]::Matches($cx,[regex]::Escape($aSig))).Count -eq 1) -and (([regex]::Matches($cx,[regex]::Escape($aRet))).Count -eq 1))) { $canPatch=$false }
    if (-not $clDone -and ([regex]::Matches($cl,[regex]::Escape($aCall))).Count -ne 1) { $canPatch=$false }
    if ($canPatch) {
      if (-not $cxDone) { $cx=$cx.Replace($aWrite,'    const next = previous; // '+$marker).Replace($aSig,'export function codexAdapterStatus(workspace) { // '+$marker) }
    $check=@'
    if (!mcpRegistered && workspace?.root) {
        try {
            const projectConfig = fs.readFileSync(path.join(workspace.root, ".codex", "config.toml"), "utf8");
            mcpRegistered = /\[mcp_servers\.awehitch\]/.test(projectConfig);
        }
        catch {
            // This workspace has no project-level Codex registration.
        }
    }
'@
      if (-not $cxDone) { $check=($check -replace "`r`n","`n").TrimEnd(); $cx=$cx.Replace($aRet,$check+"`n"+$aRet); BackupOnce $codex; WriteUtf8 $codex $cx }
      if (-not $clDone) { $cl=$cl.Replace($aCall,'            const status = impl.status(workspace); // '+$marker); BackupOnce $cli; WriteUtf8 $cli $cl }
      Row "补丁 4 项目级配置" "缺陷或半完成状态" "已补上" "逐文件补齐用户级写入与项目级状态检查"
    } else { Row "补丁 4 项目级配置" "判不准" "未动" "未完成文件的锚点不唯一" }
  }
}

# 补丁 7：安装技能的 Boot 为 1700 字节且无 [C2C]，真实发送返回 INVALID_MESSAGE。
$template = Join-Path $root "skill\SKILL.md.template"; $marker='PATCH(local): valid C2C boot prompt'
if (-not (Test-Path $template)) { Row "补丁 7 消息格式" "找不到文件" "未动" "缺 SKILL.md.template" }
else {
  $text=ReadUtf8 $template
  if ($text.Contains($marker)) { Row "补丁 7 消息格式" "已处理" "跳过" "已有本地补丁标记" }
  else {
    $pattern='(?s)(### Boot prompt \(send once per new ChatGPT conversation\)\s*```\s*).*?(\s*```)(?=\s*## Workflow)'
    $line='Use the "{{CONNECTOR_NAME}}" connector: call workspace_info (pass workspace=<name> if list_workspaces shows several) and read a hello-style top-level file. Reply with the workspace name.'
    if (([regex]::Matches($text,$pattern)).Count -eq 1 -and ([regex]::Matches($text,[regex]::Escape($line))).Count -eq 1) {
      $boot=@'
[C2C]
STATE: BOOT
You are the planning and review layer. The local agent owns editing, shell,
git and tests; you own reasoning, planning and independent review.
Read the workspace through the "{{CONNECTOR_NAME}}" connector.
1. Read needed files, git status and diff yourself; never ask for pasted copies.
2. Reply with C2C states: PLAN, DONE or BLOCKED.
3. Give a concise executable plan with rationale, file-level suggestions,
   meaningful risks and test advice.
4. After EXECUTED, verify the real diff and tests; do not trust success claims.
5. Iterate until the success criteria hold.
6. HANDOFF continues an existing task: re-read code and resume its next step.
<!-- PATCH(local): valid C2C boot prompt -->
'@
      $boot=($boot -replace "`r`n","`n").Trim(); $text=[regex]::Replace($text,$pattern,{param($m) $m.Groups[1].Value+$boot+$m.Groups[2].Value},1)
      $text=$text.Replace($line,"[C2C]`nSTATE: CONNECT_CHECK`n"+$line)
      BackupOnce $template; WriteUtf8 $template $text
      Row "补丁 7 消息格式" "缺陷仍在" "已补上" "Boot 已压缩，工作区校验已加 [C2C] 头"
    } else { Row "补丁 7 消息格式" "判不准" "未动" "Boot 或工作区校验锚点不唯一" }
  }
}

# 补丁 7 同一缺陷的快速问答入口：模板明确调用 send_state，却要求省略 [C2C]。
if (Test-Path $template) {
  $text=ReadUtf8 $template
  $quickOld=@'
Quick question — answer in plain language; no [C2C] message needed.
<the user's question, with any context ChatGPT cannot see>
'@
  $quickNew=@'
[C2C]
STATE: QUICK_QUESTION
Answer in plain language; the response does not need C2C formatting.
<the user's question, with any context ChatGPT cannot see>
'@
  $quickOld=($quickOld -replace "`r`n","`n").Trim(); $quickNew=($quickNew -replace "`r`n","`n").Trim()
  if ($text.Contains($quickNew)) { Row "补丁 7 快速问答格式" "已处理" "跳过" "快速问答已有 [C2C] 头" }
  elseif (([regex]::Matches($text,[regex]::Escape($quickOld))).Count -eq 1) {
    BackupOnce $template; WriteUtf8 $template $text.Replace($quickOld,$quickNew)
    Row "补丁 7 快速问答格式" "缺陷仍在" "已补上" "真实发送的 INVALID_MESSAGE 已修正"
  } else { Row "补丁 7 快速问答格式" "判不准" "未动" "快速问答锚点不唯一或已改版" }
}

# 只更新本次实测所用、且已经存在的 Codex 技能。
$skill=Join-Path $env:USERPROFILE ".codex\skills\awehitch\SKILL.md"
if ((Test-Path $template) -and (Test-Path $skill) -and -not ($rows | Where-Object {$_.自检 -eq "判不准"})) {
  $rendered=(ReadUtf8 $template).Replace("{{HARNESS}}","Codex").Replace("{{CONNECTOR_NAME}}","awehitch")
  if ((ReadUtf8 $skill) -ne $rendered) { WriteUtf8 $skill $rendered; Row "Codex 技能" "与模板不一致" "已更新" "只重渲染现有 Codex 技能" }
  else { Row "Codex 技能" "与模板一致" "跳过" "无需更新" }
}
$rows | Format-Table -AutoSize | Out-String | Write-Host
$bad=$rows | Where-Object {$_.自检 -in @("判不准","找不到文件")}
if ($bad) { throw "有 $($bad.Count) 项未修改，需要重新适配。" }
Write-Host "完成：只处理了 0.3.2 上有真实失败证据的补丁 1、3、4、7。" -ForegroundColor Green
