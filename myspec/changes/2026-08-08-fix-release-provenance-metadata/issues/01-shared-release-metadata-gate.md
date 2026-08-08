# 01 — 共享发布仓库元数据门禁

## Parent

- GitHub Issue（GitHub 问题）#234：https://github.com/liuli195/my-agent-skills/issues/234

## What to build

让维护者通过 Release Flow（发布流程）的项目校验、发布前检查或发布命令时，都能使用同一规则验证待发布 npm（软件包管理器）包的仓库地址和包目录；错误配置必须在触发远端发布前停止并给出明确恢复动作。

## Acceptance criteria

- [ ] 项目校验检查所有已登记且实际存在的 npm 包；发布前检查只检查本次选择发布的 npm 包。
- [ ] 仓库地址缺失、错误仓库、错误大小写、包目录缺失或错误均返回稳定错误、清单位置、期望值、实际值和恢复动作。
- [ ] HTTPS（安全超文本传输协议）、SSH（安全外壳协议）、`git+https` 和可选 `.git` 后缀能解析为大小写敏感的 GitHub（代码托管平台）仓库身份。
- [ ] 无法确定 GitHub 仓库身份时失败关闭。
- [ ] 元数据错误时，发布命令不得触发远端工作流。
- [ ] 远端发布计划继续在候选包打包前执行同一发布前检查。
- [ ] 真实命令行 Red/Green（红灯/绿灯）回归覆盖全部成功和失败场景。

## Blocked by

- None — can start immediately

**Status:** ready-for-agent
