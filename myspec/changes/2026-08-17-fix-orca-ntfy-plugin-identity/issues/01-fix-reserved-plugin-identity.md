# 01 — 修正 Orca ntfy 插件保留标识

**What to build:** 让现有 ntfy（通知服务）个人插件使用 Orca（代理运行平台）允许安装的非保留标识，并通过真实安装入口进入权限预览。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [x] 插件清单标识为 `ntfy-notifications`，版本为 `1.0.2`，其他通知行为和权限保持不变。
- [x] 现有清单测试先对旧标识形成可复现失败，再验证新标识和版本通过。
- [x] Build and Verify（构建与验证）快速验证通过且至少执行一个检查。
- [x] Orca 的真实插件安装入口成功复制插件并显示权限预览；权限批准和启用留给用户亲自完成。

## 验证证据

- 红灯：`node --test tests/orca_ntfy.test.mjs` 仅清单标识检查失败，12 项通过、1 项失败。
- 绿灯：同一命令 13 项全部通过。
- 快速验证：固定基线后的 Build and Verify（构建与验证）执行 `verify.local-build-contract` 和 `verify.runtime-boundaries`，Python（编程语言）83 项与 Node（运行环境）17 项全部通过，状态为 `passed`（通过）。
- 真实入口：Orca 识别 `liuli195.ntfy-notifications` v1.0.2，并显示 `events:subscribe`（事件订阅）与 `secrets`（私密存储）权限预览。
- 未验证：插件尚未由用户批准和启用，本轮未发送真实 ntfy 通知。
