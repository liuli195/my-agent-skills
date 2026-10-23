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
myspec state-init <work-dir> <add|review|audit> <specs-fingerprint> <input-fingerprint> [--import-aborted <archive-dir>]
myspec state-set-conflicts <work-dir> <conflicts-file> <specs-fingerprint> <input-fingerprint>
myspec state-current <work-dir> <specs-fingerprint> <input-fingerprint>
myspec state-decide <work-dir> <expected-conflict-id> <accept|ignore|defer> <specs-fingerprint> <input-fingerprint>
myspec state-decide <work-dir> <expected-conflict-id> accept-modified <specs-fingerprint> <input-fingerprint> --modified-content <完整候选正文>
myspec state-status <work-dir> <specs-fingerprint> <input-fingerprint>
myspec state-status <work-dir> <saved-specs-fingerprint> <saved-input-fingerprint> --abort-identity
myspec state-abort <work-dir> <target-worktree> <specs-dir> <delta-dir> <preview-dir> <state-sha256> <add|review|audit> --confirm-no-active-session
myspec validate-main <specs-dir>
myspec validate-delta <delta-dir> <specs-dir>
myspec apply-delta <specs-dir> <delta-dir> <preview-dir> <work-dir> <specs-fingerprint> <input-fingerprint>
myspec diff <specs-dir> <preview-dir>
```

`myspec apply-delta` 先用于独立预览目录。最终确认后，将输出目录设为主规格目录以执行带失败恢复的原子替换。任何非零返回码都必须停止流程并保留工作区。

## 会话恢复

1. 初始化前保存内容不得放在会被覆盖的位置；`state-init`（会话初始化）发现已有 `current`（当前会话）内容时明确拒绝，不递归删除。初始化失败只撤回本次实际创建且仍匹配的锁，保留已有草案和诊断材料。
2. 放弃失败预览前，使用保存的旧指纹运行 `state-status --abort-identity`（读取中止身份），展示目标工作树、工作根、规格根、Delta（增量规格）根、预览根、精确状态文件 SHA-256（安全散列）及锁命令。它只读身份，绝不判断会话是否仍活动。必须另外取得调用方明确的“无活动会话”确认，才可传入 `--confirm-no-active-session`（确认无活动会话）。
3. `state-abort`（会话中止）逐项匹配上述身份。Delta 和预览必须位于该工作根的 `current` 内；不接受重定向路径、其他工作树、未知状态、缺少基线或已进入正式应用的会话。当前主规格必须仍等于保存的原内容基线，规格父目录不得存在 `.my-spec-backup-*`（规格备份）或 `.my-spec-preview-*`（待替换规格）现场。输入或失败预览变化不阻止归档，不得修改旧指纹来假装仍有效。
4. 旧版只有 `add`、`review` 或 `audit` 命令文字加单个换行的锁，可以使用相同命令恢复，但必须精确提供旧状态和全部路径，并通过原主规格基线及无部分应用现场核验。不得补写旧状态不存在的会话身份或应用阶段来伪造兼容。任一证据不足均保留原锁、状态及草案。
5. 工具先将完整 `current` 原子移入工作根内唯一的 `aborted/<状态散列>-<唯一标识>/current`（已中止归档），保留决定、Delta、预览及失败文件，再删除仍精确匹配的锁。归档失败保留原会话和锁；归档后解锁失败时，归档与锁均保留，用相同参数重试只完成匹配的解锁。重复请求不得覆盖旧归档，也不得影响后来出现的新会话。
6. 使用返回的归档目录显式运行 `state-init ... --import-aborted <archive-dir>`（导入已中止草案）。只允许同工作根的完整归档，只复制 Delta 内容。新会话使用当前证据和主规格指纹、全新身份及 `ANALYZING`（分析中）状态，旧冲突、决定、就绪状态和最终确认均不继承。先重新分析并保存完整候选、逐项决定、校验 Delta、生成预览并展示完整差异，仍须等待新的最终确认才可正式应用。

中止不恢复已进入正式应用的事务。正式替换前会记录应用阶段；异常或中断后即使已自动回滚，仍不能用预览中止释放该现场。保留材料并按受控事务恢复处理，不提供忽略身份的解锁或强制解锁。

正式替换及校验成功后才清理本次草案。最终解锁失败时仍保留完整草案并回滚主规格；已校验提交之后的草案或备份清理失败则报告实际残留，不将其说成已清理，也不回滚已经提交的主规格。

## 开发模式多工作树

开发模式的裸 `myspec` 是机器级单一源码绑定，不会按当前目录自动切换。绑定源码后，任意目标工作树都直接运行该实现；无需为目标工作树重复切换绑定：

```text
myspec init --dev --source <源码工作树>
myspec doctor
```

`doctor`（诊断）中的 `binding`（绑定）报告会列出源码工作树、源码提交、目标工作树、目标提交和 `worktreeMatch`（工作树匹配结果），`toolchain.implementationIdentity`（工具链实现身份）只由 MySpec 实际受控运行内容决定。`worktreeMatch` 仅供诊断，不再阻止跨工作树预览或应用。每次运行首次生成预览时固定目标工作树、规格根、Delta 根、预览根、规格与输入指纹及实现身份；继续或应用时任一项漂移、预览缺失、跨工作树路径或实现身份无法确认都必须返回非零结果。实现身份变化后重新生成预览，差异不变可沿用确认，差异改变必须重新确认。单一全局绑定仍不支持并行切换源码；各工作树的 `.local/spec-work/` 锁继续相互隔离。
