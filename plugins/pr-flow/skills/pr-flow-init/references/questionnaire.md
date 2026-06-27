# PR Flow Init Questionnaire

## 场景：初次启用 PR Flow（拉取请求流程）

固定问题：目标分支是哪一个？

固定选项：
- `main`: 默认主分支。
- `master`: 旧仓库主分支。
- 自定义分支名：只在用户明确提供时使用。

选择后果：写入 `defaults.baseBranch`（默认目标分支）和 `branches.<branch>`（分支覆盖）。

跳转规则：继续 review gate（审查门禁）场景。

## 场景：选择 review gate（审查门禁）

固定问题：PR Flow（拉取请求流程）合并前使用哪种审查门禁？

固定选项：
- `github`: 依赖 GitHub（代码托管平台）required review（必需审查）。
- `local`: 依赖本地 `review-pass.json`（审查通过文件）。
- `dual`: 同时要求 GitHub（代码托管平台）和本地证据。
- `skip`: 只允许明确的小改或特殊仓库使用。

选择后果：写入 `defaults.reviewGate.mode`（默认审查门禁模式）；`local` 和 `dual` 必须写入 `defaults.reviewGate.evidencePath`（审查证据路径）。

跳转规则：继续 hotfix（热修复）场景。

## 场景：启用 hotfix（热修复）直推

固定问题：是否允许目标分支 hotfix（热修复）直推？

固定选项：
- `false`: 默认，不允许。
- `true`: 只在用户明确授权时允许。

选择后果：`true` 必须写入 `branches.<branch>.allowHotfixPush: true`（允许热修复直推）、`authorization`（授权短语哈希）、`hotfix.verifyCommand`（热修复验证命令）和 `remote`（远端名），并生成 Rulesets bypass（规则集绕过权限）建议。

跳转规则：继续 cleanup（清理）场景。

## 场景：配置 cleanup（清理）行为

固定问题：GitHub（代码托管平台）是否也启用 auto-delete head branch（自动删除源分支）？

固定选项：
- `false`: 由 PR Flow cleanup（清理）命令负责。
- `true`: 输出职责重叠 warning（警告）。

选择后果：写入 `setup.github.autoDeleteHeadBranch`（GitHub 自动删除源分支建议），不作为运行命令输入。

跳转规则：继续 GitHub setup suggestions（GitHub 配置建议）场景。

## 场景：GitHub setup suggestions（GitHub 配置建议）

固定问题：需要哪些远端规则建议？

固定选项：
- protected branches（受保护分支）。
- required checks（必需检查）。
- required review（必需审查）。
- allowed merge methods（允许合并方式）。
- Rulesets bypass（规则集绕过权限）。

选择后果：只写入 `setup.github`（GitHub 配置建议），complete、cleanup、hotfix、tweak 和 diagnose（收尾、清理、热修复、小改、诊断）不得消费。

跳转规则：继续最终写入确认。

## 场景：最终写入确认

固定问题：是否确认写入 `.pr-flow/config.yaml`、`.pr-flow/pr-template.md` 和 `.pr-flow/.gitignore`？

固定选项：
- `yes`: 仅在 validate（校验）没有 error（错误）时写入。
- `no`: 停止，不写入。

选择后果：用户沉默 MUST NOT 被视为确认。

跳转规则：`yes` 运行 init（初始化）写入；`no` 停止。
