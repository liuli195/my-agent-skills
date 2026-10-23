# 07 — 接通源码仓库 CI 与发布

**What to build:** MySpec（自有规格）贡献者能够在本地完整验证和 PR CI（拉取请求持续集成）中测试当前检出提交生成的真实 npm 软件包；发布维护者只能发布已经通过该主流程验证的同版本 CLI（命令行程序）与 Agent Plugin（代理插件）。

**Blocked by:** 06 — 迁移 Skill 与 Plugin Sync.

**Status:** ready-for-agent

- [ ] 本地快速验证可直接覆盖源码，但完整验证必须生成、隔离安装并调用当前提交的 npm Tarball（npm 软件包）。
- [ ] PR CI（拉取请求持续集成）检出 PR 当前测试合并提交并安装该提交打出的软件包，不调用机器预装版、npm 最新发布版或上一发布版 MySpec（自有规格）。
- [ ] Build and Verify（构建与验证）只作为统一构建与验证入口执行已配置检查，不承担 MySpec（自有规格）版本推断或同步职责。
- [ ] 完整自动化验证通过安装后 CLI（命令行程序）覆盖既有规格业务命令、初始化、诊断、模式切换、更新限制、锁和中断恢复。
- [ ] 真实 Agent（代理）端到端回归从发布模式进入开发模式，验证 Pi、Claude、Codex 使用可观察的本地变化，再恢复保存版本并确认无重复 Skill（技能）。
- [ ] 现有 Release Workflow（发布工作流）只在完整发布形态验证通过后发布 npm 包、Git Tag（Git 标签）和 GitHub Release（发布版本）记录。
- [ ] 发布不生成 Wheel（Python 安装包）、Pi ZIP（Pi 压缩包）或 MySpec（自有规格）自建发布资产缓存。
