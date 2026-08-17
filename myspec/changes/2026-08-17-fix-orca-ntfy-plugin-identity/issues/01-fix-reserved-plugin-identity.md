# 01 — 修正 Orca ntfy 插件保留标识

**What to build:** 让现有 ntfy（通知服务）个人插件使用 Orca（代理运行平台）允许安装的非保留标识，并通过真实安装入口进入权限预览。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 插件清单标识为 `ntfy-notifications`，版本为 `1.0.2`，其他通知行为和权限保持不变。
- [ ] 现有清单测试先对旧标识形成可复现失败，再验证新标识和版本通过。
- [ ] Build and Verify（构建与验证）快速验证通过且至少执行一个检查。
- [ ] Orca 的真实插件安装入口成功复制插件并显示权限预览；权限批准和启用留给用户亲自完成。
