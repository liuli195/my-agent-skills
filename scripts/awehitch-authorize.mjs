#!/usr/bin/env node
/**
 * awehitch 授权补位脚本（ChatGPT 侧连接器授权）
 *
 * 为什么需要它
 * ------------
 * awehitch 的 `awehitch up` / `connector-setup` 内置了"创建连接器 + 授权"的自动化，
 * 但在本机实测**授权这一步会静默失败**：它点完「连接」后找不到授权页，流程中断，
 * 且不会给出可操作的线索（复现 3 次）。
 *
 * 已定位到的原因之一（中文界面下的选择器多重命中）已通过
 * `%LOCALAPPDATA%\awehitch\control-plane\selectors.json` 修复；修好后仍存在残留问题。
 * 本脚本用**已验证可用的固定序列**完成同一件事，作为补位手段。
 *
 * 什么时候用
 * ----------
 * - 新增工作区、`awehitch up` 卡在授权步骤时
 * - 隧道地址变化后重建了连接器（连接器已存在但未授权）时
 *
 * 使用前提
 * --------
 * 1. 该工作区的桥接与隧道已在运行（`awehitch doctor -w <workspace> --json` 为绿）
 * 2. ChatGPT 连接器**已存在**（本脚本只做授权，不建连接器）
 * 3. 控制面浏览器已登录 ChatGPT
 *
 * 用法
 * ----
 *   node scripts/awehitch-authorize.mjs "<工作区绝对路径>" "<连接器名>"
 *
 * 例：
 *   node scripts/awehitch-authorize.mjs "D:\My Project\Quant-Research-Lab" "awehitch · Quant-Research-Lab"
 *
 * 退出码：0 = 授权完成；1 = 失败（输出里会说明断在哪一步）
 */
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import path from "node:path";
import process from "node:process";

// 复用 awehitch 自带的 Playwright，避免另装一份浏览器自动化依赖
const require = createRequire("C:/Users/liuli/AppData/Roaming/npm/node_modules/awehitch/");
const { chromium } = require("playwright");

const NODE = process.execPath;
const CLI = "C:\\Users\\liuli\\AppData\\Roaming\\npm\\node_modules\\awehitch\\dist\\cli\\index.js";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const [, , WS, NAME] = process.argv;
if (!WS || !NAME) {
  console.error('用法: node scripts/awehitch-authorize.mjs "<工作区绝对路径>" "<连接器名>"');
  process.exit(2);
}

const profile = path.join(
  process.env.LOCALAPPDATA,
  "awehitch",
  "control-plane",
  "browser-profile",
  "shared"
);

const ctx = await chromium.launchPersistentContext(profile, {
  channel: "chrome",
  headless: false,
  // 本机必须带 --force-device-scale-factor=1，否则 Playwright 的点击全被判定为"被遮挡"。
  // 同样的参数打在了 awehitch 的 dist/control-plane/browser.js 里（见 docs/research）。
  args: ["--disable-blink-features=AutomationControlled", "--force-device-scale-factor=1"],
});

try {
  const page = ctx.pages()[0] ?? (await ctx.newPage());

  console.log("1. 打开连接器设置页 …");
  await page.goto("https://chatgpt.com/#settings/Connectors", {
    waitUntil: "domcontentloaded",
    timeout: 90_000,
  });
  await sleep(8_000);

  console.log(`2. 点开连接器「${NAME}」…`);
  await page.locator(`:text-is("${NAME}")`).first().click({ timeout: 15_000 });
  await sleep(3_000);

  console.log("3. 点「连接」…");
  await page
    .locator("button:has-text('Connect'), button:has-text('连接')")
    .first()
    .click({ timeout: 15_000 });
  await sleep(3_000);

  console.log("4. 在同意弹窗里点「使用 … 登录」…");
  // 必须唯一命中：宽松的 '登录' 会同时匹配设置侧栏的「账户安全与登录」，
  // 而 Playwright 对多重命中会拒绝点击（这正是 awehitch 内置流程失败的原因之一）。
  await page
    .locator(
      "[role='dialog']:has-text('添加到 ChatGPT') button:has-text('登录'), button:has-text('使用 awehitch')"
    )
    .first()
    .click({ timeout: 15_000 });

  console.log("5. 等授权页出现 …");
  let authPage = null;
  for (let i = 0; i < 40; i++) {
    await sleep(500);
    authPage = ctx.pages().find((p) => p.url().includes("/oauth/authorize"));
    if (authPage) break;
  }
  if (!authPage) {
    console.error("   ✗ 授权页没出现——确认该连接器确实已创建，且隧道可达");
    process.exitCode = 1;
  } else {
    console.log("   ✓ 授权页已出现");

    console.log("6. 现取一个配对码（配对码约 5 分钟有效，必须现取）…");
    const out = execFileSync(NODE, [CLI, "pair", "-w", WS, "--json"], { encoding: "utf8" });
    const code = JSON.parse(out).pairingCode;
    console.log(`   配对码: ${code}`);

    console.log("7. 填入并提交 …");
    await authPage.locator("#pairing_code").fill(code);
    await authPage.locator("form button[type='submit']").click();

    for (let i = 0; i < 40; i++) {
      await sleep(500);
      if (!authPage.url().includes("/oauth/authorize")) break;
    }
    const ok = !authPage.url().includes("/oauth/authorize");
    if (ok) {
      console.log("   ✓ 授权完成");
      console.log(`\n可用下面这条确认令牌已发放：auth\\<workspaceId>.json 里 tokens 数量 > 0`);
    } else {
      console.error("   ✗ 仍停在授权页——配对码可能被拒，重跑一次即可");
      process.exitCode = 1;
    }
  }
} finally {
  await sleep(2_000);
  await ctx.close();
}
