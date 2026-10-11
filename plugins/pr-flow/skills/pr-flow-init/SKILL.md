---
name: pr-flow-init
description: "初始化 PR Flow（拉取请求流程）本地配置、PR 模板和运行态忽略文件。Use when 需要为仓库启用 PR Flow 配置。"
---

# PR Flow Init

## Hard Boundaries

- 只准备和写入 PR Flow（拉取请求流程）本地配置。
- 不提交、不推送、不合并。
- 不调用 GitHub API（GitHub 接口）写入远端设置。
- 不运行 diagnose、complete、cleanup、hotfix 或 tweak（诊断、收尾、清理、热修复、小改）。
- GitHub Rulesets（GitHub 规则集）只输出 remote tasks（远端待办）。
- 禁止在当前对话未获得用户明确确认时修改 GitHub Rulesets（GitHub 规则集）、branch protection（分支保护）、workflow variables（工作流变量）或 repository settings（仓库设置）；未确认时只能输出 remote tasks（远端待办）。
- 开发模式工具链必须提供可由 CI（持续集成）检出的精确实现提交和实现闭包身份；缺少该提交时，在写入任何 PR Flow 文件前安全停止并提示先发布实现提交。源码工作树也可以作为初始化目标工作树。

## Closed Loop

agent（代理）必须完成问答、草案展示、只读 validate（校验）、校验摘要、最终确认和本地写入结果说明。用户沉默 MUST NOT 被视为确认。

即使仓库已存在 `.pr-flow/config.yaml`（配置文件），也不得跳过问答、草案展示、只读 validate（校验）、校验摘要和最终确认；现有配置、分支状态或历史记录只能作为参考，不能代替用户回答或确认。

## Required Flow

1. 读取 `references/questionnaire.md`（问答模板）。
2. 按固定问题收集运行配置和 `setup.github`（GitHub 配置建议）意图。
3. 读取 `references/config-draft.md`（配置草案规则）并展示 `.pr-flow/config.yaml`（配置文件）草案。
4. 读取 `references/validation.md`（校验规则）并运行只读 `validate --config <path>`（校验配置）。
5. 如果 validate（校验）有 error（错误），停止，不写入。
6. 展示 warning（警告）或 remote tasks（远端待办）的影响（如有），并在最终确认前明确说明初始化还会新增 `.pr-flow/toolchain.json`（工具链身份记录）和 `.github/workflows/pr-flow-toolchain.yml`（工具链工作流）。
7. 用户明确确认后，运行 `init --project <repo> --config <path>`（初始化写入配置）。

## Output

- `.pr-flow/config.yaml`（配置文件）。
- `.pr-flow/pr-template.md`（拉取请求模板）。
- `.pr-flow/.gitignore`（忽略文件）。
- `.pr-flow/toolchain.json`（工具链身份记录）。
- `.github/workflows/pr-flow-toolchain.yml`（工具链工作流）。
- GitHub（代码托管平台）remote tasks（远端待办）摘要，不声明已执行。

## References

- `references/questionnaire.md`
- `references/config-draft.md`
- `references/validation.md`
