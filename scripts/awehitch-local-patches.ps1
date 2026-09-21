<#
.SYNOPSIS
  重放 awehitch 0.3.2 上经过真实入口验证的本地补丁。
.DESCRIPTION
  重放在干净 0.3.2 上复现并验证的补丁 1、3、4、7，同时管理授权按钮覆盖与安全观测。
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

# 授权按钮选择器：只管理 connector.signInButton，保留其余用户覆盖。
$stateRoot = if ($env:AWEHITCH_STATE_DIR) { [IO.Path]::GetFullPath($env:AWEHITCH_STATE_DIR) } elseif ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "awehitch" } else { $null }
$selectorFile = if ($stateRoot) { Join-Path $stateRoot "control-plane\selectors.json" } else { $null }
$signInButton = @(
  "[role='dialog']:has-text('添加到 ChatGPT') button:has-text('登录')",
  "button:has-text('使用 awehitch')",
  "[role='dialog']:has-text('Add ') button:has-text('Sign in')",
  "[role='alertdialog'] button:has-text('Sign in')"
)
if (-not $selectorFile) { Row "授权按钮选择器" "判不准" "未动" "无法确定 awehitch 状态目录" }
elseif (-not (Test-Path $selectorFile)) {
  $selectorDir = Split-Path $selectorFile -Parent
  New-Item -ItemType Directory -Path $selectorDir -Force | Out-Null
  $data = [ordered]@{ connector = [ordered]@{ signInButton = $signInButton } }
  $temp = Join-Path $selectorDir ("selectors.{0}.tmp" -f ([guid]::NewGuid().ToString("N")))
  try { WriteUtf8 $temp ($data | ConvertTo-Json -Depth 20); Move-Item -LiteralPath $temp -Destination $selectorFile -Force }
  finally { if (Test-Path $temp) { Remove-Item -LiteralPath $temp -Force } }
  Row "授权按钮选择器" "缺少覆盖" "已补上" "新建覆盖文件，仅写入授权按钮候选"
}
else {
  $rawSelector = ReadUtf8 $selectorFile
  try { $data = $rawSelector | ConvertFrom-Json -ErrorAction Stop }
  catch { $data = $null }
  $validRoot = $rawSelector.TrimStart().StartsWith("{") -and $data -and -not ($data -is [array])
  $hasConnector = $validRoot -and $data.PSObject.Properties.Name -contains "connector"
  $connector = if ($hasConnector) { $data.connector } else { $null }
  $validConnector = (-not $hasConnector) -or $connector -is [pscustomobject]
  $hasSignIn = $validConnector -and $connector -and $connector.PSObject.Properties.Name -contains "signInButton"
  $existing = if ($hasSignIn) { @($connector.signInButton) } else { @() }
  if (-not $validRoot) { Row "授权按钮选择器" "判不准" "未动" "selectors.json 不是有效的 JSON 对象" }
  elseif (-not $validConnector) { Row "授权按钮选择器" "判不准" "未动" "connector 不是有效的 JSON 对象" }
  elseif ($hasSignIn) {
    $same = $existing.Count -eq $signInButton.Count
    for ($i=0; $same -and $i -lt $signInButton.Count; $i++) { $same = [string]$existing[$i] -ceq $signInButton[$i] }
    if ($same) { Row "授权按钮选择器" "已处理" "跳过" "授权按钮候选与正式配置一致" }
    else { Row "授权按钮选择器" "判不准" "未动" "已有不同的 signInButton 覆盖，拒绝覆盖" }
  }
  else {
    if (-not $connector) { $connector = [pscustomobject]@{}; $data | Add-Member -NotePropertyName connector -NotePropertyValue $connector }
    $connector | Add-Member -NotePropertyName signInButton -NotePropertyValue $signInButton
    $selectorDir = Split-Path $selectorFile -Parent
    $temp = Join-Path $selectorDir ("selectors.{0}.tmp" -f ([guid]::NewGuid().ToString("N")))
    try { BackupOnce $selectorFile; WriteUtf8 $temp ($data | ConvertTo-Json -Depth 20); Move-Item -LiteralPath $temp -Destination $selectorFile -Force }
    finally { if (Test-Path $temp) { Remove-Item -LiteralPath $temp -Force } }
    Row "授权按钮选择器" "缺少覆盖" "已补上" "保留未知字段，只合并授权按钮候选"
  }
}

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

# 授权观测：记录每个安全阶段的结果，不记录网址、配对码、令牌或原始错误消息。
$connectorFile = Join-Path $root "dist\control-plane\connector.js"
$authMarker = 'PATCH(local): observe connector authorization safely and wait for consent'
$legacySafeAuthMarker = 'PATCH(local): observe connector authorization safely'
$partialAuthMarker = 'PATCH(local): observe connector authorization clicks'
$authImport = 'import { ControlPlaneBrowser } from "./browser.js";'
$authSleep = 'const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));'
$authFlow = @'
    await match.rows[0].locator("button").first().click().catch(() => undefined);
    await sleep(1_500);
    const connect = await targetLocator(ctx.page, ctx.site, "connectButton");
    if (connect && (await connect.count().catch(() => 0)) > 0) {
        await connect.click().catch(() => undefined);
        await sleep(1_200);
    }
    // The consent dialog ("Add <name> to ChatGPT") carries the real trigger.
    const signIn = await targetLocator(ctx.page, ctx.site, "signInButton");
    if (signIn && (await signIn.count().catch(() => 0)) > 0) {
        await signIn.click().catch(() => undefined);
    }
'@
$authFlow = ($authFlow -replace "`r`n","`n").TrimEnd()
$observedFlow = @'
    await match.rows[0].locator("button").first().click().catch(() => undefined);
    await sleep(1_500);
    const connectSelector = await targetSelector(ctx.page, ctx.site, "connectButton");
    const connect = connectSelector ? ctx.page.locator(connectSelector).first() : null;
    const connectCount = connect ? await connect.count().catch(() => 0) : 0;
    if (connect && connectCount > 0) {
        try {
            await connect.click();
            authObserver.info("[AUTH-OBS] connect-click", { count: connectCount, ok: true });
        }
        catch (error) {
            authObserver.warn("[AUTH-OBS] connect-click", { count: connectCount, ok: false, errorType: authObservationErrorType(error) });
        }
        await sleep(1_200);
    }
    else {
        authObserver.warn("[AUTH-OBS] connect-click", { count: connectCount, ok: false, errorType: "target-not-found" });
    }
    // The consent dialog ("Add <name> to ChatGPT") carries the real trigger.
    const signInStartedAt = Date.now();
    const signInDeadline = signInStartedAt + 10_000;
    let signInHit = null;
    while (!signInHit && Date.now() < signInDeadline) {
        await sleep(500);
        signInHit = await resolveConnectorTarget(ctx.page, ctx.site.connector, "signInButton");
    }
    const signIn = signInHit ? ctx.page.locator(signInHit.selector).first() : null;
    const signInCount = signInHit?.count ?? 0;
    const signInVisible = signIn ? await signIn.isVisible().catch(() => false) : false;
    authObserver.info("[AUTH-OBS] sign-in-state", { waitMs: Date.now() - signInStartedAt, count: signInCount, visible: signInVisible });
    if (signIn && signInCount > 0) {
        try {
            await signIn.click();
            authObserver.info("[AUTH-OBS] sign-in-click", { count: signInCount, visible: signInVisible, ok: true });
        }
        catch (error) {
            authObserver.warn("[AUTH-OBS] sign-in-click", { count: signInCount, visible: signInVisible, ok: false, errorType: authObservationErrorType(error) });
        }
    }
    else {
        authObserver.warn("[AUTH-OBS] sign-in-click", { count: signInCount, visible: signInVisible, ok: false, errorType: "target-not-found" });
    }
'@
$observedFlow = ($observedFlow -replace "`r`n","`n").TrimEnd()
$legacyObservedFlow = @'
    await match.rows[0].locator("button").first().click().catch(() => undefined);
    await sleep(1_500);
    const connectSelector = await targetSelector(ctx.page, ctx.site, "connectButton");
    const connect = connectSelector ? ctx.page.locator(connectSelector).first() : null;
    const connectCount = connect ? await connect.count().catch(() => 0) : 0;
    if (connect && connectCount > 0) {
        try {
            await connect.click();
            authObserver.info("[AUTH-OBS] connect-click", { selector: connectSelector, count: connectCount, ok: true });
        }
        catch (error) {
            authObserver.warn("[AUTH-OBS] connect-click", { selector: connectSelector, count: connectCount, ok: false, error: authObservationError(error) });
        }
        await sleep(1_200);
    }
    else {
        authObserver.warn("[AUTH-OBS] connect-click", { selector: connectSelector, count: connectCount, ok: false, error: "target-not-found" });
    }
    // The consent dialog ("Add <name> to ChatGPT") carries the real trigger.
    const signInHit = await resolveConnectorTarget(ctx.page, ctx.site.connector, "signInButton");
    const signIn = signInHit ? ctx.page.locator(signInHit.selector).first() : null;
    const signInCount = signInHit?.count ?? 0;
    const signInVisible = signIn ? await signIn.isVisible().catch(() => false) : false;
    authObserver.info("[AUTH-OBS] sign-in-state", { delayMs: 1200, selector: signInHit?.selector ?? null, count: signInCount, visible: signInVisible });
    if (signIn && signInCount > 0) {
        try {
            await signIn.click();
            authObserver.info("[AUTH-OBS] sign-in-click", { selector: signInHit.selector, count: signInCount, visible: signInVisible, ok: true });
        }
        catch (error) {
            authObserver.warn("[AUTH-OBS] sign-in-click", { selector: signInHit.selector, count: signInCount, visible: signInVisible, ok: false, error: authObservationError(error) });
        }
    }
    else {
        authObserver.warn("[AUTH-OBS] sign-in-click", { selector: signInHit?.selector ?? null, count: signInCount, visible: signInVisible, ok: false, error: "target-not-found" });
    }
'@
$legacyObservedFlow = ($legacyObservedFlow -replace "`r`n","`n").TrimEnd()
$legacyObservedFlowSafe = $legacyObservedFlow.Replace('authObservationError(error)','authObservationErrorType(error)').Replace('error: authObservationErrorType(error)','errorType: authObservationErrorType(error)').Replace('error: "target-not-found"','errorType: "target-not-found"')
$setupAnchor = @'
export async function runConnectorSetup(opts) {
    const site = opts.site ?? loadSiteSelectors().site;
'@
$setupAnchor = ($setupAnchor -replace "`r`n","`n").TrimEnd()
$setupObserved = @'
export async function runConnectorSetup(opts) {
    const loadedSelectors = loadSiteSelectors();
    const site = opts.site ?? loadedSelectors.site;
    authObserver.info("[AUTH-OBS] selectors-loaded", {
        source: opts.site ? "injected" : loadedSelectors.source,
        siteId: site.id,
        siteVersion: site.version,
        candidateCount: Array.isArray(site.connector.signInButton) ? site.connector.signInButton.length : 1,
        problemCount: opts.site ? 0 : loadedSelectors.problems.length,
    });
'@
$setupObserved = ($setupObserved -replace "`r`n","`n").TrimEnd()
$authorizeAnchor = '                const authorizePage = await waitForAuthorizePage(ctx.page, ctx.authorizeTimeoutMs, ctx.verifyAuthorized);'
$authorizeObserved = $authorizeAnchor + "`n" + '                authObserver.info("[AUTH-OBS] authorize-page", { found: Boolean(authorizePage) });'
$verifyAnchor = '            if (!authorized) {'
$verifyObserved = $verifyAnchor + "`n" + '                authObserver.warn("[AUTH-OBS] authorization-verify", { ok: false, errorType: "not-authorized" });'
$finalAnchor = @'
    const ok = steps.every((step) => step.status === "done" || step.status === "skipped");
    return { ok, dryRun: false, steps, connectorName: currentName, manualFallback: ok ? undefined : fallback() };
'@
$finalAnchor = ($finalAnchor -replace "`r`n","`n").TrimEnd()
$finalObserved = @'
    const ok = steps.every((step) => step.status === "done" || step.status === "skipped");
    authObserver.info("[AUTH-OBS] authorization-verify", {
        ok,
        authorizeStatus: steps.find((step) => step.id === "authorize")?.status ?? "missing",
        verifyStatus: steps.find((step) => step.id === "verify")?.status ?? "missing",
    });
    return { ok, dryRun: false, steps, connectorName: currentName, manualFallback: ok ? undefined : fallback() };
'@
$finalObserved = ($finalObserved -replace "`r`n","`n").TrimEnd()
if (-not (Test-Path $connectorFile)) { Row "授权链路观测" "找不到文件" "未动" "缺 connector.js" }
else {
  $text = ReadUtf8 $connectorFile
  $complete = $text.Contains($authMarker) -and $text.Contains('const signInDeadline = signInStartedAt + 10_000;') -and $text.Contains('[AUTH-OBS] selectors-loaded') -and $text.Contains('[AUTH-OBS] connect-click') -and $text.Contains('[AUTH-OBS] sign-in-state') -and $text.Contains('[AUTH-OBS] sign-in-click') -and $text.Contains('[AUTH-OBS] authorize-page') -and $text.Contains('[AUTH-OBS] authorization-verify') -and $text.Contains('authObservationErrorType')
  if ($complete) { Row "授权链路观测" "已处理" "跳过" "安全观测阶段齐全" }
  else {
    $canPatch = $true
    if ($text.Contains($partialAuthMarker) -or $text.Contains($legacySafeAuthMarker)) {
      $unsafeError = 'const authObservationError = (error) => error instanceof Error ? error.message : String(error);'
      $safeError = 'const authObservationErrorType = (error) => error instanceof Error ? error.name : typeof error;'
      $legacyFlow = if (([regex]::Matches($text,[regex]::Escape($legacyObservedFlow))).Count -eq 1) { $legacyObservedFlow } elseif (([regex]::Matches($text,[regex]::Escape($legacyObservedFlowSafe))).Count -eq 1) { $legacyObservedFlowSafe } else { $null }
      $hasUnsafeError = ([regex]::Matches($text,[regex]::Escape($unsafeError))).Count -eq 1
      $hasSafeError = ([regex]::Matches($text,[regex]::Escape($safeError))).Count -eq 1
      if (-not $legacyFlow -or (-not $hasUnsafeError -and -not $hasSafeError)) { $canPatch = $false }
      else {
        $text = $text.Replace($partialAuthMarker,$authMarker).Replace($legacySafeAuthMarker,$authMarker).Replace($legacyFlow,$observedFlow)
        if ($text.Contains($unsafeError)) { $text = $text.Replace($unsafeError,$safeError) }
        $text = $text.Replace('authObservationError(error)','authObservationErrorType(error)').Replace('error: authObservationErrorType(error)','errorType: authObservationErrorType(error)').Replace('error: "target-not-found"','errorType: "target-not-found"')
        $text = $text.Replace('signInCandidates: site.connector.signInButton,','candidateCount: Array.isArray(site.connector.signInButton) ? site.connector.signInButton.length : 1,').Replace('problems: opts.site ? [] : loadedSelectors.problems,','problemCount: opts.site ? 0 : loadedSelectors.problems.length,')
      }
    }
    else {
      $clean = (([regex]::Matches($text,[regex]::Escape($authImport))).Count -eq 1) -and (([regex]::Matches($text,[regex]::Escape($authSleep))).Count -eq 1) -and (([regex]::Matches($text,[regex]::Escape($authFlow))).Count -eq 1) -and (([regex]::Matches($text,[regex]::Escape($setupAnchor))).Count -eq 1)
      if (-not $clean) { $canPatch = $false }
      else {
        $text = $text.Replace($authImport,$authImport+"`n"+'import { Logger } from "../logger/index.js"; // '+$authMarker)
        $text = $text.Replace($authSleep,$authSleep+"`n"+'const authObserver = new Logger({ name: "connector-auth-observer", console: false });'+"`n"+'const authObservationErrorType = (error) => error instanceof Error ? error.name : typeof error;')
        $text = $text.Replace($authFlow,$observedFlow).Replace($setupAnchor,$setupObserved)
      }
    }
    foreach ($pair in @(@($authorizeAnchor,$authorizeObserved),@($verifyAnchor,$verifyObserved),@($finalAnchor,$finalObserved))) {
      if (-not $canPatch) { break }
      if ($text.Contains($pair[1])) { continue }
      if (([regex]::Matches($text,[regex]::Escape($pair[0]))).Count -ne 1) { $canPatch = $false; break }
      $text = $text.Replace($pair[0],$pair[1])
    }
    $finalComplete = $text.Contains($authMarker) -and $text.Contains('const signInDeadline = signInStartedAt + 10_000;') -and $text.Contains('[AUTH-OBS] selectors-loaded') -and $text.Contains('[AUTH-OBS] connect-click') -and $text.Contains('[AUTH-OBS] sign-in-state') -and $text.Contains('[AUTH-OBS] sign-in-click') -and $text.Contains('[AUTH-OBS] authorize-page') -and $text.Contains('[AUTH-OBS] authorization-verify') -and $text.Contains('authObservationErrorType') -and -not $text.Contains('authObservationError =')
    if (-not $finalComplete) { $canPatch = $false }
    if ($canPatch) { BackupOnce $connectorFile; WriteUtf8 $connectorFile $text; Row "授权链路观测" "缺少完整观测" "已补上" "覆盖选择器、点击、授权页和最终桥接验证" }
    else { Row "授权链路观测" "判不准" "未动" "授权链路锚点不唯一或已有未知改动" }
  }
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

# 补丁 4：awehitch up 实测改写 ~/.codex/config.toml；本仓库使用固定的项目级注册。
$codex = Join-Path $root "dist\adapters\codex.js"; $cli = Join-Path $root "dist\cli\index.js"
$marker = 'PATCH(local): keep Codex registration project-local and validate complete fixed project config'
$previousMarker = 'PATCH(local): keep Codex registration project-local and validate fixed project config'
$legacyMarker = 'PATCH(local): keep Codex registration project-local'
$aWrite = '    const next = upsertCodexMcpEntry(previous, opts.cliEntry, opts.workspaceRoot);'
$aSig = 'export function codexAdapterStatus() {'
$aRet = '    return { skillInstalled: fs.existsSync(skillPath), mcpRegistered, sandboxAllowed, configPath };'
$aCall = '            const status = impl.status();'
$legacyWrite = '    const next = previous; // '+$legacyMarker
$legacySig = 'export function codexAdapterStatus(workspace) { // '+$legacyMarker
$legacyCall = '            const status = impl.status(workspace); // '+$legacyMarker
$previousWrite = '    const next = previous; // '+$previousMarker
$previousSig = 'export function codexAdapterStatus(workspace) { // '+$previousMarker
$previousCall = '            const status = impl.status(workspace); // '+$previousMarker
$legacyCheck = @'
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
$legacyCheck=($legacyCheck -replace "`r`n","`n").TrimEnd()
$previousValidator = @'
function hasValidProjectRegistration(content, workspaceRoot) { // PATCH(local): validate fixed project registration
    const header = /^[ \t]*\[mcp_servers\.awehitch\][ \t]*$/m.exec(content);
    if (!header || !workspaceRoot)
        return false;
    const afterHeader = header.index + header[0].length;
    const rest = content.slice(afterHeader);
    const next = /^[ \t]*\[[^\]]+\][ \t]*$/m.exec(rest);
    const table = content.slice(header.index, next ? afterHeader + next.index : content.length);
    if (/^[ \t]*type[ \t]*=[ \t]*["']stdio["'][ \t]*$/m.test(table))
        return false;
    const workspaceMatch = /"--workspace"\s*,\s*"((?:\\.|[^"\\])*)"/.exec(table);
    if (!workspaceMatch || !/"--harness"\s*,\s*"codex"/.test(table))
        return false;
    if (!/AWEHITCH_MAX_PARALLEL_SESSIONS\s*=\s*["']3["']/.test(table))
        return false;
    const configuredRoot = workspaceMatch[1].replace(/\\\\/g, "\\").replace(/\\"/g, '"');
    const normalize = value => path.resolve(String(value)).replace(/[\\/]+$/, "").toLowerCase();
    return normalize(configuredRoot) === normalize(workspaceRoot);
}
'@
$previousValidator=($previousValidator -replace "`r`n","`n").TrimEnd()
$validator = @'
function hasValidProjectRegistration(content, workspaceRoot) { // PATCH(local): validate complete fixed project registration
    const header = /^[ \t]*\[mcp_servers\.awehitch\][ \t]*$/m.exec(content);
    if (!header || !workspaceRoot)
        return false;
    const afterHeader = header.index + header[0].length;
    const rest = content.slice(afterHeader);
    const next = /^[ \t]*\[[^\]]+\][ \t]*$/m.exec(rest);
    const table = content.slice(header.index, next ? afterHeader + next.index : content.length);
    if (/^[ \t]*type[ \t]*=[ \t]*["']stdio["'][ \t]*$/m.test(table))
        return false;
    const argsLine = /^[ \t]*args[ \t]*=[ \t]*\[([^\r\n]*)\][ \t]*(?:#.*)?$/m.exec(table);
    const envLine = /^[ \t]*env[ \t]*=[ \t]*\{([^\r\n]*)\}[ \t]*(?:#.*)?$/m.exec(table);
    if (!argsLine || !envLine)
        return false;
    const workspaceMatch = /"--workspace"\s*,\s*"((?:\\.|[^"\\])*)"/.exec(argsLine[1]);
    if (!workspaceMatch || !/"--harness"\s*,\s*"codex"/.test(argsLine[1]))
        return false;
    if (!/AWEHITCH_CONTROL_PLANE\s*=\s*["']1["']/.test(envLine[1]))
        return false;
    if (!/AWEHITCH_MAX_PARALLEL_SESSIONS\s*=\s*["']3["']/.test(envLine[1]))
        return false;
    const configuredRoot = workspaceMatch[1].replace(/\\\\/g, "\\").replace(/\\"/g, '"');
    const normalize = value => path.resolve(String(value)).replace(/[\\/]+$/, "").toLowerCase();
    return normalize(configuredRoot) === normalize(workspaceRoot);
}
'@
if (-not (Test-Path $codex) -or -not (Test-Path $cli)) { Row "补丁 4 项目级配置" "找不到文件" "未动" "缺 Codex 适配器文件" }
else {
  $cx=ReadUtf8 $codex; $cl=ReadUtf8 $cli
  $cxDone=$cx.Contains('const next = previous; // '+$marker) -and $cx.Contains('function hasValidProjectRegistration(content, workspaceRoot)') -and $cx.Contains('mcpRegistered = hasValidProjectRegistration(projectConfig, workspace.root);')
  $clDone=$cl.Contains('const status = impl.status(workspace); // '+$marker)
  $cxPrevious=(-not $cxDone) -and (([regex]::Matches($cx,[regex]::Escape($previousWrite))).Count -eq 1) -and (([regex]::Matches($cx,[regex]::Escape($previousValidator+"`n"+$previousSig))).Count -eq 1)
  $clPrevious=(-not $clDone) -and (([regex]::Matches($cl,[regex]::Escape($previousCall))).Count -eq 1)
  $cxLegacy=(-not $cxDone) -and (([regex]::Matches($cx,[regex]::Escape($legacyWrite))).Count -eq 1) -and (([regex]::Matches($cx,[regex]::Escape($legacySig))).Count -eq 1) -and (([regex]::Matches($cx,[regex]::Escape($legacyCheck+"`n"+$aRet))).Count -eq 1)
  $clLegacy=(-not $clDone) -and (([regex]::Matches($cl,[regex]::Escape($legacyCall))).Count -eq 1)
  if ($cxDone -and $clDone) { Row "补丁 4 项目级配置" "已处理" "跳过" "两个文件均有完整最终特征" }
  else {
    $canPatch=$true
    if ($cxPrevious) { $cx=$cx.Replace($previousWrite,$aWrite).Replace($previousValidator+"`n"+$previousSig,$aSig) }
    elseif ($cxLegacy) { $cx=$cx.Replace($legacyWrite,$aWrite).Replace($legacySig,$aSig).Replace($legacyCheck+"`n"+$aRet,$aRet) }
    elseif (-not $cxDone -and $cx.Contains($legacyMarker)) { $canPatch=$false }
    if ($clPrevious) { $cl=$cl.Replace($previousCall,$aCall) }
    elseif ($clLegacy) { $cl=$cl.Replace($legacyCall,$aCall) }
    elseif (-not $clDone -and $cl.Contains($legacyMarker)) { $canPatch=$false }
    if (-not $cxDone -and -not ((([regex]::Matches($cx,[regex]::Escape($aWrite))).Count -eq 1) -and (([regex]::Matches($cx,[regex]::Escape($aSig))).Count -eq 1) -and (([regex]::Matches($cx,[regex]::Escape($aRet))).Count -eq 1))) { $canPatch=$false }
    if (-not $clDone -and ([regex]::Matches($cl,[regex]::Escape($aCall))).Count -ne 1) { $canPatch=$false }
    if ($canPatch) {
      if (-not $cxDone) {
        $status=@'
    let mcpRegistered = false;
    let sandboxAllowed = false;
    try {
        const content = fs.readFileSync(configPath, "utf8");
        sandboxAllowed = isStateDirAllowlisted(content, getStateDir());
    }
    catch {
        // missing config -> sandbox status remains false
    }
    if (workspace?.root) {
        try {
            const projectConfig = fs.readFileSync(path.join(workspace.root, ".codex", "config.toml"), "utf8");
            mcpRegistered = hasValidProjectRegistration(projectConfig, workspace.root);
        }
        catch {
            // This workspace has no valid project-level Codex registration.
        }
    }
    return { skillInstalled: fs.existsSync(skillPath), mcpRegistered, sandboxAllowed, configPath };
'@
        $status=($status -replace "`r`n","`n").TrimEnd()
        $statusStart=$cx.IndexOf("    let mcpRegistered = false;")
        $statusEnd=$cx.IndexOf($aRet,$statusStart)
        if ($statusStart -lt 0 -or $statusEnd -lt $statusStart) {
          Row "补丁 4 项目级配置" "判不准" "未动" "状态函数范围无法唯一定位"
          $canPatch=$false
        } else {
          $statusEnd += $aRet.Length
          $oldStatus=$cx.Substring($statusStart,$statusEnd-$statusStart)
          $newStatus=$status.TrimEnd()
          $cx=$cx.Replace($aWrite,'    const next = previous; // '+$marker).Replace($aSig,($validator -replace "`r`n","`n").TrimEnd()+"`nexport function codexAdapterStatus(workspace) { // "+$marker).Replace($oldStatus,$newStatus)
          BackupOnce $codex; WriteUtf8 $codex $cx
        }
      }
      if ($canPatch) {
        if (-not $clDone) { $cl=$cl.Replace($aCall,'            const status = impl.status(workspace); // '+$marker); BackupOnce $cli; WriteUtf8 $cli $cl }
        Row "补丁 4 项目级配置" "缺陷或半完成状态" "已补上" "阻止用户级写入并语义检查固定项目配置"
      }
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

# 稳态流程：固定项目配置不靠 up 切换；先查全机状态，只在停止、未登记或诊断明确要求时修复。
if (Test-Path $template) {
  $text=ReadUtf8 $template
  $statusMarker='PATCH(local): status-first steady-state workflow'
  $failureOld=@'
5. If something fails, run `awehitch doctor -w <workspace> --json` and repair
   silently. Only involve the user for logins, CAPTCHA, or 2FA — and then give
   them ONE action at a time.
'@
  $failureNew=@'
5. If something fails, run `awehitch status --json`, then
   `awehitch doctor -w <workspace> --no-fix --json`. Follow the reported repair
   only when it names one; never turn a timeout into connector rebuild. Only
   involve the user for logins, CAPTCHA, or 2FA — one action at a time.
'@
  $quickFlowOld=@'
1. Run `awehitch up -w <workspace> --json --daemon`. Idempotent: reuses the
   running service or starts it in the background; the address, connector and
   pairing survive restarts. `ok: false` with `needsLogin: true` → ONE action:
   "Log in to ChatGPT in the opened window, then tell me 'done'", then re-run.
   Any other failure → `awehitch doctor -w <workspace> --json` and follow its
   repair guidance.
'@
  $quickFlowNew=@'
1. Run `awehitch status --json`. If the service is running and this workspace
   is registered, do not run `up`. Otherwise run
   `awehitch doctor -w <workspace> --no-fix --json`; run `up -w <workspace>
   --json --daemon` only when the service is stopped or the workspace is not
   registered, and run connector repair only when the diagnosis names it.
   `needsLogin: true` → ONE action: ask the user to log in, then retry the
   reported command. <!-- PATCH(local): status-first steady-state workflow -->
'@
  $codingFlowOld=@'
0. `awehitch doctor -w <workspace> --json` (auto-repairs). Doctor gate: if
   local is not green, do not open ChatGPT and do not send INIT. Follow its
   `chatgptRepair` / `namedRepair` guidance first.
'@
  $codingFlowNew=@'
0. Run `awehitch status --json`. If the service is running and this workspace
   is registered, continue without `up`. Otherwise run `awehitch doctor -w
   <workspace> --no-fix --json`; do not open ChatGPT or send INIT until green.
   Run only the specific `up`, `chatgptRepair` or `namedRepair` action reported.
'@
  $failureOld=($failureOld -replace "`r`n","`n").Trim(); $failureNew=($failureNew -replace "`r`n","`n").Trim()
  $quickFlowOld=($quickFlowOld -replace "`r`n","`n").Trim(); $quickFlowNew=($quickFlowNew -replace "`r`n","`n").Trim()
  $codingFlowOld=($codingFlowOld -replace "`r`n","`n").Trim(); $codingFlowNew=($codingFlowNew -replace "`r`n","`n").Trim()
  if ($text.Contains($statusMarker)) { Row "稳态状态优先" "已处理" "跳过" "正常流程不会无条件运行 up" }
  elseif ((([regex]::Matches($text,[regex]::Escape($failureOld))).Count -eq 1) -and (([regex]::Matches($text,[regex]::Escape($quickFlowOld))).Count -eq 1) -and (([regex]::Matches($text,[regex]::Escape($codingFlowOld))).Count -eq 1)) {
    BackupOnce $template
    $text=$text.Replace($failureOld,$failureNew).Replace($quickFlowOld,$quickFlowNew).Replace($codingFlowOld,$codingFlowNew)
    WriteUtf8 $template $text
    Row "稳态状态优先" "仍会无条件启动或修复" "已补上" "状态检查后才按诊断执行 up 或连接器修复"
  } else { Row "稳态状态优先" "判不准" "未动" "失败、快速问答或开发任务锚点不唯一" }
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
Write-Host "完成：已处理 0.3.2 补丁 1、3、4、7、授权按钮覆盖与安全观测。" -ForegroundColor Green
