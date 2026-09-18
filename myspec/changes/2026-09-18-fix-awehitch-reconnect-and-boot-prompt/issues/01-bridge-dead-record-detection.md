# 01 — bridge 认得出「记录已死」

**What to build:** 重启电脑或隧道失效之后，Agent（代理）照技能流程走能真的把连接恢复起来。当前第一处阻塞是：本工作区那份**陈旧的运行记录**让 bridge（桥接服务）**拒绝启动**——记录里的端口已被**另一个工作区**占用，于是判为「状态不明」。本票据让 bridge 认得出「记录里的进程已经死了」，此时直接判「已停止」并正常启动新实例。同时建立本次改动的测试接缝。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [x] 记录里的进程**已死**时，`awehitch status -w <仓库> --json` 报「已停止」，而不是「状态不明」。
- [x] 记录里的进程号**被系统回收**（该号码现在属于无关进程）时，**仍保持保守**：判「状态不明」并拒绝启动。这是本次**明确不修**的一支，验收时确认它没被误改。
- [x] 端口被别的实例占用、但本记录的进程已死时，新实例能启动，并**自行退到临时端口**，不打断那个占用者。
      （**由源码确认，未由运行检查覆盖**：`dist/bridge/server.js` 在 `EADDRINUSE` 时回退到临时端口。
      真实冒烟里 bridge 正常起来了，但没有专门构造"端口被占"这一场景。）
- [x] 新增的检查挂进**既有的** `verify.build-and-verify`：按**文件名**加入，**不使用通配**。
- [x] **未新增**构建或验证入口，沿用既有入口。
- [x] 改动以本地补丁形式进入 `scripts/awehitch-local-patches.ps1`：幂等、带自检、判不准不动手、可从 `.orig` 重放。
- [x] 红灯证据与绿灯证据来自**同一入口**（命令行进、JSON 出）：红灯 `assert None is False` → 绿灯 `1 passed`。
- [x] 一个提交（`bfa13b82`）。

**Spec reference:** `myspec/changes/2026-09-18-fix-awehitch-reconnect-and-boot-prompt/spec.md`
