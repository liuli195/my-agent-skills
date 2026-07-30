# MySpec 规则

## 主规格

主规格固定为 `myspec/specs/<capability-name>/spec.md`。能力目录使用 `kebab-case`（短横线命名），一个能力只有一个 `spec.md`。

每个文件必须包含 `# <Capability>`、`## Purpose`、`## Requirements`。每个 `### Requirement: <标题>` 的标题在规格库全局唯一，是有语义的身份；正文必须包含 `MUST` 或 `SHALL`，并至少包含一个具有非空 `WHEN` 和 `THEN` 的 `#### Scenario:`。

只记录用户或外部系统可观察、可验证的行为。内部文件、类型、函数、算法、计划和待办事项不进入规格。

## Delta

Delta（增量规格）按能力放在 `.local/spec-work/current/delta/<capability-name>/spec.md`，只允许：

- `## RENAMED Requirements`：连续的 `FROM: <旧标题>`、`TO: <新标题>` 对。
- `## REMOVED Requirements`：用 Requirement（需求）标题引用。
- `## MODIFIED Requirements`：写出完整的新 Requirement（需求）。
- `## ADDED Requirements`：写出完整的新 Requirement（需求）。

应用固定按 `RENAMED → REMOVED → MODIFIED → ADDED`。新能力的 Delta（增量规格）还必须包含 `# <Capability>` 和非空 `## Purpose`。

只有证据明确声明改名时使用 `RENAMED`。否则标题变化按 `REMOVED + ADDED`，其中删除逐条确认。只允许自动修复标题层级、空行、尾随空格、文件末尾换行和区块顺序；不得猜写缺失语义。

## 确定性命令

直接调用 `PATH`（可执行文件搜索路径）中的 CLI（命令行程序）；不得定位或解析包内脚本：

```text
myspec state-init <work-dir> <add|review|audit> <specs-fingerprint> <input-fingerprint>
myspec state-set-conflicts <work-dir> <conflicts-file> <specs-fingerprint> <input-fingerprint>
myspec state-current <work-dir> <specs-fingerprint> <input-fingerprint>
myspec state-decide <work-dir> <expected-conflict-id> <accept|ignore|defer> <specs-fingerprint> <input-fingerprint>
myspec state-decide <work-dir> <expected-conflict-id> accept-modified <specs-fingerprint> <input-fingerprint> --modified-content <完整候选正文>
myspec state-status <work-dir> <specs-fingerprint> <input-fingerprint>
myspec validate-main <specs-dir>
myspec validate-delta <delta-dir> <specs-dir>
myspec apply-delta <specs-dir> <delta-dir> <preview-dir> <work-dir> <specs-fingerprint> <input-fingerprint>
myspec diff <specs-dir> <preview-dir>
```

`myspec apply-delta` 先用于独立预览目录。最终确认后，将输出目录设为主规格目录以执行带失败恢复的原子替换。任何非零返回码都必须停止流程并保留工作区。
