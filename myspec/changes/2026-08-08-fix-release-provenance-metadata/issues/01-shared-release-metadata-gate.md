# 01 — 共享发布仓库元数据门禁

## Parent

- GitHub Issue（GitHub 问题）#234：https://github.com/liuli195/my-agent-skills/issues/234

## What to build

让维护者通过 Release Flow（发布流程）的项目校验、发布前检查或发布命令时，都能使用同一规则验证待发布 npm（软件包管理器）包的仓库地址和包目录；错误配置必须在触发远端发布前停止并给出明确恢复动作。

## Acceptance criteria

- [x] 项目校验检查所有已登记且实际存在的 npm 包；发布前检查只检查本次选择发布的 npm 包。
- [x] 仓库地址缺失、错误仓库、错误大小写、包目录缺失或错误均返回稳定错误、清单位置、期望值、实际值和恢复动作。
- [x] HTTPS（安全超文本传输协议）、SSH（安全外壳协议）、`git+https` 和可选 `.git` 后缀能解析为大小写敏感的 GitHub（代码托管平台）仓库身份。
- [x] 无法确定 GitHub 仓库身份时失败关闭。
- [x] 元数据错误时，发布命令不得触发远端工作流。
- [x] 远端发布计划继续在候选包打包前执行同一发布前检查。
- [x] 真实命令行 Red/Green（红灯/绿灯）回归覆盖全部成功和失败场景。

## Behavior evidence

- Red（红灯）：恢复审查后的首次统一验证发现 5 个失败，证明本地与 GitHub Actions（GitHub 自动化任务）身份来源需要分离，且旧测试环境会遮蔽该行为。
- Green（绿灯）：`build-and-verify verify --project .` 检查 4 项且状态为 `passed`；`verify.release-flow` 98 项、`verify.runtime-boundaries` 11 项通过。
- User-entry smoke（用户入口冒烟）：当前仓库 `release-flow validate` 返回 `status: verified`；临时错误仓库返回 `status: issues`、稳定错误和 `nextAction`（下一步动作）。
- Review（审查）：Standards（规范）与 Spec（规格）发现的环境信任、URL（网址）严格性、清单位置和恢复命令问题均已修复；最终定向复审无阻塞。
- Unresolved risk（未解决风险）：无。

## Blocked by

- None — can start immediately

**Status:** ready-for-agent
