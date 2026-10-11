## Context

### 根源定位

Issue（问题）#141 的直接现象是 Cross Agent Review（跨代理审查）输入噪音过大。抽样中 60 个实际审查输入里有 48 个出现“文档差异大于全部非文档差异”，文档占比中位数约为 61.2%；PR（拉取请求）#142 首轮文档占比约 61.1%，单个计划文件达到 1272 行。这个推测成立，但 Comet（双星工作流）生成文档只是放大器，不是最上游根因。

最上游根因位于 Cross Agent Review（跨代理审查）的输入契约：历史提交 `dd2e1397` 为简化流程删除了 changed-file manifest（变更文件清单）和 path-scoped diff（路径限定差异）模板，却保留了面向两个角色的无范围完整 `git diff`（差异命令）。当前实现只把规格、设计和计划路径写入 `review-input.json`（审查输入文件），提示词仍让两个角色读取相同的完整差异。因此任何上游流程只要生成较多文档，都会制造相同噪音；在 Comet（双星工作流）内部过滤文档只能掩盖一个调用方。

Issue（问题）#149 的根源是 Cross Agent Review（跨代理审查）把两个角色放在一次 SDK dispatch（开发包派发）中，且只在整次派发结束后写报告，没有逐角色持久状态。一个角色超时会让另一个已经成功的结果失去可复用边界，后续只能整轮重跑。Comet（双星工作流）计划复选框不同步是可能触发后续提交的上游现象，但不应通过侵入 Comet（双星工作流）解决审查重跑。

Issue（问题）#150 的完整 `HEAD`（提交头）绑定是有意的安全边界，不是缺陷。真正缺少的是一个只接受可机械证明变化的跨提交复用机制。曾出现只有一个计划文件发生 26 行增加、26 行删除，但第二次审查仍重放 48 个文件、5028 行差异并在未变测试上产生新发现，说明应减少无意义重审，而不是放宽提交绑定。

证据写入还存在所有权倒置：Cross Agent Review（跨代理审查）的 `mark-pass`（标记通过）硬编码了 Agent Guard（代理守卫）的画像、产物、路径和 `guard-evidence/v1`（守卫证据第一版）字段。现行 Agent Guard（代理守卫）规格又写成“只读不写”。正确边界是主代理作出语义结论，Agent Guard（代理守卫）在显式请求下执行通用、无判断的机械写入。

### 约束

- 不修改 Comet（双星工作流）的技能、五阶段链、状态文件、阶段脚本或推进逻辑。
- 不按 `.md`（标记文档）扩展名、文件大小或 Comet（双星工作流）目录硬编码排除文件。
- 不弱化当前完整 `HEAD`（提交头）校验、12 位短提交路径或干净工作区要求。
- 不让 Cross Agent Review（跨代理审查）或 Planning Review（规划审查）决定或写入 Agent Guard（代理守卫）证据。
- 不新增数据库、配置框架、插件系统或第三方依赖。
- 不安装或同步用户级 Plugin（插件）和 Guard Profile（守卫画像）。

## Goals / Non-Goals

**Goals（目标）：**

- 让两个审查角色只接收与职责相关、可追溯的输入范围，并把过程文档从主要差异降为带理由的摘要信息。
- 让角色成功结果在另一角色失败或超时时立即持久化，并可只重试失败角色。
- 对严格声明且可机械证明的提交间变化复用上一提交的审查事实，同时为当前提交生成新报告和状态。
- 让 Agent Guard（代理守卫）提供唯一通用证据写入入口，供不同审查流程的主代理复用。
- 保持现有门禁证据路径、`guard-evidence/v1`（守卫证据第一版）和平面字段检查兼容。

**Non-Goals（非目标）：**

- 不减少或改变 Comet（双星工作流）生成的规格、设计、计划和流程文档。
- 不让插件自动解析发现项并决定 `PASS`（放行）或 `BLOCKED`（阻断）。
- 不允许任意脚本、正则替换或用户代码作为跨提交复用校验器。
- 不把 Planning Review（规划审查）改造成可写技能。
- 不自动迁移、安装或发布用户当前的 `comet-review-gate`（双星审查门禁）画像。

## Decisions

### 1. 在审查输入边界消噪，不修改 Comet（双星工作流）

`review-input.json`（审查输入文件）保留现有必填字段，并增加两个可选声明：

- `summary_only`（仅摘要）：精确路径与非空理由的列表。调用方只能声明“主要审查时仅看摘要”，不能真正排除；审查代理仍可按需读取原文或差异。
- `revalidation_policy`（重新校验策略）：精确路径到受限校验器的声明，只供跨提交 `revalidate`（重新校验）使用。

插件从 Git（版本控制）差异生成单一文件清单，并按以下优先级分类：

1. `spec_file`（规格文件）、`design_file`（设计文件）和 `plan_file`（计划文件）的精确路径属于内部 `authoritative_context`（权威上下文）。
2. 调用方明确声明且带理由的路径属于 `summary_only`（仅摘要）。
3. 其余路径一律属于 `full_review`（完整审查）。

重复、越界、缺失或互相重叠的声明直接拒绝。未分类文件不得静默跳过。角色提示词不再包含无范围完整差异，也不内联文件清单；它只引用 `review-input.json`（审查输入文件）、`review-state.json`（审查状态文件）和一个由插件执行的短 role-input（角色输入）命令。该命令从状态文件读取精确路径，并通过参数数组调用 Git（版本控制），避免跨平台 shell（命令壳）转义问题。

`spec-alignment`（规格对齐）角色始终获得三份权威上下文、`full_review`（完整审查）差异和 `summary_only`（仅摘要）清单及理由；`implementation-correctness`（实施正确性）角色以 `full_review`（完整审查）差异为主要输入，按需读取权威上下文和摘要文件。两者都能按需扩展到摘要文件，因此这是噪音投影，不是审查豁免。

替代方案：在 Comet（双星工作流）侧过滤 `.md`（标记文档）或固定目录。该方案改动小，但会漏掉有行为含义的文档、只修复一个调用方，并让审查插件继续接收无边界输入，因此不采用。

### 2. `review-state.json`（审查状态文件）既是清单，也是恢复边界

每个 `.local/cross-agent-review/<change>/<head_ref_short>/`（本地审查目录）包含一个原子更新的 `review-state.json`（审查状态文件），最小结构为：

```json
{
  "schema_version": "cross-agent-review-state/v1",
  "subject": {
    "change": "...",
    "mode": "convergence",
    "base_ref": "...",
    "head_ref": "...",
    "head_ref_short": "...",
    "input_file": "...",
    "input_hash": "sha256:..."
  },
  "files": [
    {
      "path": "...",
      "status": "M",
      "classification": "full_review",
      "reason": null
    }
  ],
  "roles": {
    "spec-alignment": {
      "scope": {},
      "attempts": [],
      "status": "completed",
      "output": "...",
      "output_hash": "sha256:..."
    }
  }
}
```

角色状态只使用 `completed`（完成）、`failed`（失败）、`timed_out`（超时）和 `reused`（复用）。初始派发仍可并发，但每个角色使用独立子进程；父进程在任一角色返回时立即以临时文件加原子替换写入状态。这样保持并发速度，同时不会让一个超时吞掉另一个结果。

`retry`（重试）只选择 `failed`（失败）或 `timed_out`（超时）角色；`completed`（完成）和 `reused`（复用）角色原样保留。重试范围复用该角色原有路径范围，不得扩大到另一个角色或未在原文件清单中的路径。每次尝试追加状态、时间、输出和哈希，不覆盖历史。

替代方案：只在最终报告中记录两个角色。该方案文件更少，但无法在进程超时后证明哪个角色已完成，也无法安全重试，因此不采用。

### 3. 跨提交复用只接受两种可证明的机械变化

命令形态为 `revalidate --input-file <current> --previous-state <previous>`（重新校验当前输入并引用上一状态）。它先校验上一状态的输入哈希、报告、角色输出哈希、目录与完整提交头绑定；上一状态的两个角色都必须是 `completed`（完成），不允许从 `reused`（复用）状态继续串联复用。

随后比较上一审查提交和当前提交之间的精确变化。每个变化文件必须恰好匹配一条当前输入声明的策略，且只能使用：

- `checkbox-only`（仅复选框）：文件行数、行顺序和除 Markdown task checkbox（标记任务复选框）状态外的全部内容必须相同。
- `mapping-fields-only`（仅映射字段）：文件必须是 JSON（数据文件）或 YAML（配置文件）的顶层映射；删除声明的顶层字段后，两端解析结构必须完全相同，且只有声明字段可变化。

出现未声明文件、重复策略、重命名、复制、规格或设计变化、解析失败、脏工作区、输入或输出哈希不匹配时，命令拒绝复用且不调用 SDK（开发包）。满足全部条件时，命令也不调用 SDK（开发包），而是为当前提交复制审查事实并生成新的报告和状态，两个角色状态记为 `reused`（复用），同时记录来源提交、来源状态和已验证变化。主代理仍需读取新报告并独立决定是否记录通过证据。

替代方案：允许“文档变化”或“很小的变化”自动复用。该边界不可机械验证，会把语义变化伪装成安全变化，因此不采用。

### 4. Agent Guard（代理守卫）拥有唯一通用证据写入入口

在 Agent Guard Runtime CLI（代理守卫运行时命令行）增加 `record-evidence`（记录证据）子命令。调用方必须显式提供：project（项目）、user home（用户目录）、profile source scope（画像来源范围）、profile id（画像编号）、artifact id（产物编号）、subject type（对象类型）、subject id（对象编号）、producer（生产方）和 business fields file（业务字段文件）。入口不认识 Comet（双星工作流）、Cross Agent Review（跨代理审查）、Planning Review（规划审查）或任何固定产物编号。

写入流程为：

1. 从明确的 project（项目）或 user（用户）画像目录读取 `artifacts.yaml`（产物注册文件），拒绝同名猜测和回退。
2. 要求目标产物为 `type: json`（数据类型）且 `owner: agent-guard`（代理守卫拥有），以此确认是 guard-defined evidence（守卫定义证据），不是外部流程产物。
3. 只使用画像声明的 path（路径），填充 `profile_id`、`artifact_id`、`subject_id`、当前完整 `git_head`（提交头）和 12 位 `git_head_short`（短提交头）；拒绝缺失变量、绝对路径、驱动器路径和项目目录逃逸。
4. 要求 Git（版本控制）仓库存在、当前工作区干净，并从当前仓库读取提交头，不接受调用方覆盖。
5. 读取一个 JSON object（数据对象）业务字段文件；拒绝与保留字段冲突。保留字段为 `schema_version`、`status`、`producer`、`profile_id`、`artifact_id`、`subject_type`、`subject_id`、`head_ref`、`head_ref_short` 和 `created_at`。
6. 注入 `guard-evidence/v1`（守卫证据第一版）标准字段，以同目录临时文件加原子替换写入，并返回可复制路径。

Agent Guard（代理守卫）不读取审查报告来判断发现项，也不主动生成证据；只有主代理完成语义判断并显式调用时才机械写入。Cross Agent Review（跨代理审查）的主代理把报告和状态元数据转成现有平面业务字段。Planning Review（规划审查）的主代理按其只读结果构造包含 `mode`、`scope`、`blocking`、`findings` 和 `decision` 的五字段 `review`（审查结果）对象，并同时提供门禁现有的 `blocking_findings`、`scope`、`report` 和 `report_hash` 平面字段；`report_hash` 是该五字段对象规范 JSON（数据对象）的 SHA-256（安全哈希）值。

替代方案一：保留 Cross Agent Review（跨代理审查）的 `mark-pass`（标记通过）。改动最少，但持续耦合画像路径和证据格式，Planning Review（规划审查）还要复制一套写入器，因此不采用。

替代方案二：升级到 `guard-evidence/v2`（守卫证据第二版）。结构更整齐，但会同时迫使画像、门禁和历史测试迁移；当前平面格式能表达所需信息，因此遵循 YAGNI（不做暂不需要的设计）保留第一版。

### 5. Comet review gate（双星审查门禁）只调整画像集成契约

`comet-agent-review-gate`（双星代理审查门禁）规格继续描述外部用户级 Guard Profile（守卫画像），不修改 Comet（双星工作流）本身。两个门禁继续校验相同路径形状和当前提交头：

```text
.local/guard/evidence/{profile_id}/{artifact_id}/{subject_id}/{git_head_short}/pass.json
```

唯一迁移是证据生产方式从 Cross Agent Review（跨代理审查）专用 `mark-pass`（标记通过）或手写文件，统一改为主代理显式调用 `record-evidence`（记录证据）。门禁读取和 JSON predicate（数据谓词）检查保持不变。

## Risks / Trade-offs

- [调用方把重要文件误标为 `summary_only`（仅摘要）] → 必须提供逐路径理由，未声明文件默认完整审查，两个角色仍可按需读取摘要文件；状态文件完整记录分类供审计。
- [并发角色分别写状态造成覆盖] → 只有父进程写状态，完成事件串行合并，并使用原子替换。
- [机械校验器产生假阳性] → 只支持两个白名单校验器，精确路径一对一匹配，任何歧义都拒绝；规格和设计变化无条件拒绝。
- [通用证据入口被用来伪造外部产物] → 只接受 `owner: agent-guard`（代理守卫拥有）的 JSON（数据）产物，并强制当前提交头、干净工作区和画像声明路径。
- [`guard-evidence/v1`（守卫证据第一版）继续保留平面字段重复] → 换取现有 Guard Profile（守卫画像）和门禁兼容；等出现第二个无法表达的需求再单独设计版本升级。
- [顺序迁移期间旧命令失效] → 同一变更中先增加通用入口和端到端测试，再删除 `mark-pass`（标记通过）及文档引用；不发布中间版本。

## Migration Plan

1. 先以测试固定 Cross Agent Review（跨代理审查）的分类、状态、失败角色重试和机械复用拒绝边界。
2. 实现角色化输入与 `review-state.json`（审查状态文件），保持现有 `run`（运行）报告格式可读。
3. 以测试固定 Agent Guard（代理守卫）的通用记录入口、保留字段和安全路径；实现入口并验证现有门禁仍可读取新写入文件。
4. 更新 Cross Agent Review（跨代理审查）技能与调用说明，删除 `mark-pass`（标记通过）代码、常量、测试和 Agent Guard（代理守卫）知识。
5. 只更新仓库内 Agent Guard Run（代理守卫运行）、Cross Agent Review（跨代理审查）和 `comet-agent-review-gate`（双星代理审查门禁）的集成说明与测试夹具，描述主代理如何构造业务字段并调用通用入口；完全不修改 Planning Review（规划审查）技能或任何用户级文件。
6. 从用户入口执行两条完整端到端回归：真实 Cross Agent Review（跨代理审查）报告到门禁证据；Planning Review（规划审查）五字段结果到门禁证据。再运行仓库 full（完整）验证。
7. 本变更不自动安装。后续如需同步用户级 Plugin（插件）或 Guard Profile（守卫画像），必须另行获得明确授权。

回滚时恢复 Cross Agent Review（跨代理审查）旧命令与对应说明，并删除 Agent Guard（代理守卫）新子命令；由于证据文件格式和路径未变，已生成证据无需迁移或删除。

## Open Questions

无。输入分类、复用校验器、证据所有权、兼容格式和 Comet（双星工作流）边界均已由用户确认。
