---
name: pr-flow-hotfix
description: "执行 PR Flow（拉取请求流程）hotfix（热修复）路径，在显式授权后直接推送受保护目标分支。"
---

# PR Flow Hotfix

## 边界

仅用于配置中显式允许 `allowHotfixPush: true` 的目标分支。执行前会校验 HEAD（当前提交）的基线等于远端目标分支、工作区干净、authorization phrase（授权短语）匹配，并运行 `hotfix.verifyCommand`。

逻辑命令为 `build-and-verify verify --full`（受管完整验证）时，无论是否配置工具映射，均须退出码为 0，且标准输出行首精确字段的最终值满足 `status: passed`（状态通过）、`checked`（已检查项）非空、`full-not-run: false`（完整验证未跳过）。空输出、证据缺失或不满足条件均按 `hotfix_verify_failed`（热修复验证失败）停止，不推送、不记成功审计；标准错误警告本身不导致失败。

逻辑 `build-and-verify`（构建与验证工具）消费 `PR_FLOW_TOOL_COMMANDS`（工具命令映射）后，仅从复制的子进程环境移除该变量，保留其他变量及父环境。自定义命令保持原环境及退出码语义；快速验证和其他工具模式不要求完整验证报告。

authorization phrase（授权短语）只是“我确认”的替代，不是权限边界；真正的远端写入权限仍由 GitHub 凭证和 Rulesets bypass（规则集绕过权限）决定。

authorization phrase（授权短语）必须由用户在当前对话手动输入；禁止从 memory（记忆）、history summaries（历史摘要）、logs（日志）、Issue（问题单）或 reports（报告）中读取或复用 authorization phrase（授权短语）。

命令会在验证后重新读取目标提交，未变化才把当前目标分支直接 push（推送）到配置远端。不创建 PR，不合并 PR，也不修改 MySpec（自有规格）任务。

默认保留 worktree（工作树）。`--remove-worktree`（删除工作树参数）只在推送回读成功且当前提交等于远端目标提交后生效，不查询 PR（拉取请求）；从待删除目录内运行时按输出的外部重试命令删除，且永不强制删除。若目标工作树由 Orca（工作区管理器）登记，命令优先使用 Orca（工作区管理器）的非强制删除；Orca（工作区管理器）未登记或不可用时回退 Git（版本管理）删除。已登记目标的 Orca（工作区管理器）删除失败时停止并保留诊断，不回退 Git（版本管理）删除。

## 命令

以本次加载的技能安装目录为基准，使用 `../pr-flow/scripts/pr_flow.py`，确认脚本存在。

下方填入本技能安装目录和目标项目目录的绝对路径；`--project` 始终指向用户目标项目，不指向插件目录。不切换当前目录；无法确认路径或脚本不存在时，停止并报告。

```bash
python "<本技能安装目录>/../pr-flow/scripts/pr_flow.py" hotfix --project "<目标项目目录>" --target main --authorization-phrase <phrase>
```
