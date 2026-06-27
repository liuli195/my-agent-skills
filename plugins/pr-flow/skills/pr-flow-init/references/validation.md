# PR Flow Init Validation

## validate（校验）输出

- error（错误）：配置不可用，init（初始化）必须停止且不写入。
- warning（警告）：配置可写入，但存在流程风险。
- setup suggestion（配置建议）：需要用户或 agent（代理）另行处理的 GitHub（代码托管平台）或环境事项。

## 依赖矩阵

| 场景 | validate（校验）规则 |
| --- | --- |
| hotfix（热修复） | `allowHotfixPush: true` 要求 `authorization.phraseHashAlgorithm: md5`、非空 `authorization.phraseHash`、非空 `hotfix.verifyCommand`、非空 `remote`，并输出 Rulesets bypass（规则集绕过权限）建议。 |
| review gate（审查门禁） | `github` 或 `dual` 输出 required review（必需审查）建议；`local` 或 `dual` 要求 `evidencePath`（证据路径）并输出 `review-pass.json`（审查通过文件）契约建议。 |
| checks（检查） | `wait`（等待）只控制等待；required checks（必需检查）只作为 GitHub Rulesets（GitHub 规则集）建议。 |
| merge strategy（合并方式） | `merge`、`squash`、`rebase` 输出对应 GitHub（代码托管平台）allowed merge method（允许合并方式）建议。 |
| cleanup（清理） | auto-delete head branch（自动删除源分支）和 PR Flow cleanup（清理）同时存在时输出 warning（警告）。 |
| tweak（小改） | 只跳过插件内 review gate（审查门禁），不得声称绕过远端 required review（必需审查）。 |
| fast/full verify（快速/完整验证） | full verify（完整验证）只作为显式 `hotfix.verifyCommand`（热修复验证命令）或 PR CI（拉取请求持续集成）建议，不从证据路径推断。 |

## 写入摘要

init（初始化）写入后只说明本地文件路径和 GitHub（代码托管平台）建议摘要，不声明远端已配置。
