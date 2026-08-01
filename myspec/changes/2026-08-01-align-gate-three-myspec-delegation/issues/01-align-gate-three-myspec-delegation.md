# 01 — 对齐 Gate 3 与 MySpec 委托

**Parent（父问题）：** GitHub Issue（问题）#250

**What to build（交付结果）：** Gate 3 — Enter Delivery（进入交付）复用 `my-spec-add`（新增自有规格）的最终确认，并在该技能原子应用和校验规格后才进入 Gate 4 — Authorize PR Delivery（授权 PR 交付）。

**Blocked by（阻塞项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-human

- [x] Delivery（交付）说明、技能入口与正式规格使用同一 Gate 3 顺序。
- [x] Development Flow（开发流程）只委托 `my-spec-add`（新增自有规格）的校验和恢复，不复制其程序或增加例外。
- [x] 契约检查与新 Pi（编码代理）冒烟证明该技能成功应用并校验后才进入 Gate 4。

## Behavior evidence（行为证据）

- Red（红灯）：Build and Verify（构建与验证）快速入口中的 Gate 3 契约预期失败，证明原说明要求 Gate 3 通过后才调用 `my-spec-add`（新增自有规格）。
- Green（绿灯）：同一快速入口通过；`verify.local-build-contract`（本地构建契约检查）与 `verify.myspec`（自有规格检查）均成功。
- User-entry smoke（用户入口冒烟）：新 Pi（编码代理）无会话调用读取本地 `pi-development-flow`（Pi 开发流程）技能后，在完整预览差异等待最终确认的场景中，要求使用 `my-spec-add`（新增自有规格）的原始最终确认，并确认原子应用和校验后才进入 Gate 4。
- Review（审查）：首次完整审查发现票据证据缺失和重复静态检查；两项已定向修复，规范与规格复核均无发现。
- Unresolved risk（未解决风险）：无。
