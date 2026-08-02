## 背景

代理守卫（Agent Guard）有两类约束：

1. 会话范围的流程指导：会话焦点（Session Focus）把当前对话绑定到某个守卫实例（Guard Instance），实例有自己的状态、进度和守卫简报。
2. 命令边界约束：只要主 agent 准备执行某类命令，就必须先满足项目级规则；这个判断不依赖当前会话是否绑定了某个守卫实例。

本变更属于第二类。Comet verify（Comet 验证）只是第一个用例。最终能力必须是通用的全局命令守卫点（Global Command Guard），可以守卫任何配置出来的命令点。

## 术语约定

正文使用中文名称；代码、配置键、运行时输出保留英文标识。

| 英文标识 | 中文名称 | 设计含义 |
| --- | --- | --- |
| Agent Guard | 代理守卫 | 整体守卫系统。 |
| Global Command Guard | 全局命令守卫点 | 不依赖会话焦点的命令级拦截规则。 |
| Effective Global Command Guard Set | 有效全局命令守卫集 | PreToolUse 时从所有启用来源收集出的全局命令守卫规则集合。 |
| PreToolUse | 工具使用前 | 命令执行前的拦截时机。 |
| command point | 命令点 | 需要被守卫的命令边界，例如验证、发布、部署。 |
| command pattern | 命令模式 | 用于匹配受保护命令的配置模式。 |
| named capture | 命名捕获 | 从命令中提取的变量，例如 `change`、`tag`、`environment`。 |
| command context | 命令上下文 | 从工具输入、命令文本、命名捕获和运行时环境汇总出的检查上下文。 |
| effective guard id | 有效守卫 ID | 运行时唯一规则身份，格式为 `<source_scope>:<profile_id>:<guard_id>`。 |
| evidence | 证据 | 命令放行前必须存在并通过校验的材料。 |
| evidence path template | 证据路径模板 | 使用命名捕获拼出证据路径的模板。 |
| JSON predicate | JSON 谓词 | 对 JSON 字段执行的受限检查。 |
| Session Focus | 会话焦点 | 当前会话绑定到哪个守卫实例。 |
| Guard Instance | 守卫实例 | 有独立状态和进度的流程型守卫实例。 |
| Guard Brief | 守卫简报 | 注入会话的指导信息。 |
| audit | 审计 | 守卫允许或拒绝命令的记录。 |

## 目标

- 在 PreToolUse 阶段执行全局命令守卫点，即使当前没有会话焦点。
- 保持能力通用：运行时只理解“匹配命令、提取上下文、检查证据”，不得写死 Comet、发布、部署或 review 语义。
- 支持多个 Guard Profile 同时贡献全局命令守卫点，并统一形成有效全局命令守卫集。
- 支持用户级和项目级静态规则同时存在；命中同一命令时采用叠加约束。
- 最大复用现有代理守卫能力：
  - 命令提取；
  - 命令匹配；
  - JSON 字段读取和谓词评估；
  - 运行时路径处理；
  - 审计写入；
  - 校验器问题格式。
- 保持现有会话焦点、守卫实例状态机、`state_completed`、守卫简报语义不变。

## 非目标

- 不为本需求新增 Gate Binding（门禁绑定）或守卫实例索引模型。
- 不修改 Comet 核心脚本，也不要求 Comet 命令主动调用代理守卫。
- 不要求全局命令守卫点依赖会话焦点实例。
- 不实现 review 流程本身；review 报告和通过标记属于独立变更。
- 不在守卫检查中引入任意脚本执行、表达式执行或 JSONPath 查询语言。

## 最终方案

### 1. 强制边界

全局命令守卫点由 Agent Guard 的 PreToolUse hook（工具使用前钩子）执行。主 agent 仍然执行普通 shell 命令；代理守卫在命令真正执行前拦截：

1. 从工具 envelope（信封）中提取工具名和命令文本。
2. 收集所有项目级和用户级 Guard Profile 贡献的 `global-command-guards.yaml`。
3. 为每条规则生成有效守卫 ID：`<source_scope>:<profile_id>:<guard_id>`。
4. 形成 Effective Global Command Guard Set（有效全局命令守卫集）。
5. 用配置的命令模式匹配命令，并提取命名捕获。
6. 对所有匹配的全局命令守卫点逐一解析证据路径、读取 JSON 证据并执行 JSON 谓词检查。
7. 任意匹配规则检查失败时返回 `deny`，命令不得执行。
8. 所有匹配规则都通过时，继续进入现有 Session Focus permission（会话焦点权限）逻辑。

这回答了“谁调用守卫”的问题：不是 Comet 调用，也不是主 agent 自觉调用，而是代理守卫 hook 在命令边界自动调用。

### 2. 作用域与运行目录

这里必须区分三件事：

1. Plugin install scope（插件安装范围）：插件装在个人 marketplace 还是仓库 marketplace。
2. Guard Profile scope（守卫画像范围）：静态画像放在 `.agents/guards` 还是 `~/.agents/guards`。
3. Runtime data scope（运行态数据范围）：审计、证据、会话焦点、实例状态写到哪里。

运行态数据不能简单按“插件/画像是不是用户级”决定。它应按事件或命令的目标作用域决定。

项目相关事件默认使用项目级运行目录：

```text
.local/guard
```

用户级运行目录只用于真正的用户作用域运行态：

```text
~/.agents/guard
```

判定规则：

- 当前命令或 hook 事件作用于项目时，运行时动态文件写入 `.local/guard`。这包括用户级插件、用户级 Guard Profile 在项目内触发的项目相关事件。
- 会话焦点实例只有在显式以 `scope=user` 激活或创建时，绑定、实例状态、简报和审计才写入 `~/.agents/guard`。
- 全局命令守卫点默认按命令目标选择运行目录：项目命令写 `.local/guard`；用户全局命令才写 `~/.agents/guard`。
- 如果未来配置需要强制用户级运行态，应显式声明类似 `runtime_scope: user` 的字段；不得仅因配置文件来自 `~/.agents/guards` 就自动写用户级运行目录。
- Comet change review 属于项目、change id 和 Git HEAD 相关证据，必须使用项目级 `.local/guard`。

因此，当前“Agent Guard 安装/画像都是用户级，但日志在 `.local/guard`”是合理现象：这些日志是项目上下文里的 hook 审计或无会话焦点审计，不是用户全局运行态。

如果未来同时启用项目级和用户级全局命令守卫点，同一个项目命令可分别命中两个来源的规则；但只要它守卫的是项目命令，默认证据和审计仍应落在项目 `.local/guard`，任一规则拒绝都会阻止命令执行。

### 3. 多来源收集模型

`global-command-guards.yaml` 不是“当前画像的私有规则”，而是某个 Guard Profile 对全局命令守卫系统贡献的一组规则。

PreToolUse 时，Runtime 收集以下来源：

```text
项目级来源：
.agents/guards/*/global-command-guards.yaml

用户级来源：
~/.agents/guards/*/global-command-guards.yaml
```

收集规则：

- 每个包含 `global-command-guards.yaml` 的 Guard Profile 都可以贡献 0 到多条规则。
- 收集不依赖当前 Session Focus，也不依赖当前激活的守卫实例。
- 同一文件内的 `guard_id` 必须唯一。
- 不同 profile 或不同 source scope 中允许同名 `guard_id`。
- 运行时唯一身份是有效守卫 ID：`<source_scope>:<profile_id>:<guard_id>`。

示例：

```text
project:repo-policy:verify_requires_review
user:personal-safety:verify_requires_review
```

两条规则的 `guard_id` 都是 `verify_requires_review`，但运行时身份不同，不冲突。

### 4. 评估语义

全局命令守卫点采用叠加约束，不采用覆盖语义。

如果一个命令同时匹配多个规则：

```text
所有匹配规则都必须通过。
任意一个匹配规则 deny，最终结果就是 deny。
```

不存在“项目级覆盖用户级”或“后加载覆盖先加载”。这是守卫系统，不是普通配置合并系统。

拒绝输出和审计必须包含：

- `matched_guard_ids`：所有命中的有效守卫 ID；
- `failing_guards`：失败守卫列表；
- 每个失败守卫的 source scope、profile id、guard id、evidence path、失败检查详情；
- 当前命令上下文和捕获值。

### 5. 配置模型

全局命令守卫点作为 Guard Profile 的静态配置存在，文件名固定为：

```text
.agents/guards/<profile_id>/global-command-guards.yaml
```

配置形态：

```yaml
global_command_guards:
  - id: protected_command_requires_evidence
    description: 受保护命令执行前必须有证据。
    tool: Bash
    match:
      command_patterns:
        - 'some-tool publish (?P<tag>[A-Za-z0-9._-]+)'
        - 'deploy --env (?P<environment>[A-Za-z0-9._-]+)'
      required_captures:
        - tag
    evidence:
      path: '.local/guard/evidence/{source_scope}/{profile_id}/{guard_id}/{tag}/evidence.json'
    checks:
      - field: status
        predicate: equals
        value: pass
      - field: tag
        predicate: equals
        value_from: tag
      - field: head_ref
        predicate: equals
        value_from: git_head
    deny:
      reason: global_command_guard_required
      next: produce_required_evidence
      suggestion: 先生成当前命令对应的通过证据。
```

Runtime 会为证据路径模板提供内置上下文值：

- `source_scope`：静态规则来源，`project` 或 `user`；
- `profile_id`：贡献该规则的 Guard Profile ID；
- `guard_id`：规则在本文件内的 ID；
- `effective_guard_id`：运行时唯一身份；
- `runtime_scope`：动态数据写入作用域，通常项目命令为 `project`。

Comet 的“review 后才能 verify”只是一个配置实例，可以匹配 Comet 验证相关命令并检查对应 review-pass 证据。运行时不包含 Comet 分支判断。

### 6. 能力复用与抽象

| 能力 | 当前状态 | 本变更处理 |
| --- | --- | --- |
| `command_from_envelope` / `tool_name_from_envelope` | 已存在于 PreToolUse 运行时 | 直接复用，并包装为命令上下文构建入口。 |
| `write_audit` / `runtime_root` | 已存在于运行时 | 直接复用；项目上下文审计落在 `.local/guard/audit`，显式用户作用域审计落在 `~/.agents/guard/audit`。 |
| `rule_matches` / `command_prefix` | 存在于会话焦点权限路径 | 抽象为共享命令匹配层，供会话焦点和全局命令守卫点共同使用。 |
| `json_artifact` 字段读取和谓词评估 | 存在于 Guard Point 检查路径 | 抽象为共享 JSON 检查器，支持 evidence JSON。 |
| `ValidationIssue` 风格 | 已存在于 Guard Profile 校验器 | 直接复用，新增 `global_command_guards` 校验类别或字段路径。 |
| `global-command-guards.yaml` | 不存在 | 新建，作为全局命令守卫点专属静态配置。 |
| 命名捕获、`value_from`、`git_head` | 部分不存在 | 新建为命令上下文和运行时上下文能力。 |
| 多来源收集 | 不存在 | 新建全局命令守卫收集器，生成有效全局命令守卫集。 |
| 有效守卫 ID | 不存在 | 新建 `<source_scope>:<profile_id>:<guard_id>` 规则身份。 |

### 7. 执行顺序

全局命令守卫点必须先于会话焦点权限执行：

```text
PreToolUse
  -> 构建命令上下文
  -> 收集项目级和用户级 global-command-guards.yaml
  -> 形成有效全局命令守卫集
  -> 匹配所有全局命令守卫点
      -> 未匹配：进入现有会话焦点权限
      -> 任一匹配规则证据失败：deny
      -> 所有匹配规则证据通过：进入现有会话焦点权限
  -> 现有 Session Focus permission
```

因此，全局命令守卫点是“前置项目规则”，会话焦点权限仍然是“当前会话流程规则”。两者职责不重叠。

### 8. 目录设计

目录原则：

1. 领域差异明显时分目录或分文件。
2. 项目相关运行时动态文件复用 `.local/guard`；显式用户作用域运行时动态文件使用 `~/.agents/guard`。
3. 关联紧密的文件放在只包含该关注点的目录或文件中，避免把全局命令守卫点塞进守卫实例状态目录。

#### 插件源码目录

```text
plugins/agent-guard/
  scripts/
    hook_router.py                         # 钩子入口分发；继续作为 Codex/Claude hook 的入口
    guard_runtime/                         # 运行时能力目录
      __init__.py
      cli.py                               # 运行时 CLI 入口
      core.py                              # 现有主运行时；本变更可先小步拆分
      command_context.py                   # 新建：命令上下文构建和命令文本标准化
      command_matcher.py                   # 新建：命令模式、命名捕获、前缀匹配
      json_checks.py                       # 新建或抽象：JSON 字段读取和谓词评估
      global_command_guards.py             # 新建：全局命令守卫收集、匹配、评估
      paths.py                             # 可抽象：运行时路径和 profile 路径
      audit.py                             # 可抽象：审计写入
      session_focus.py                     # 可抽象：会话焦点解析和权限检查
      instances.py                         # 可抽象：守卫实例状态读写
      state_machine.py                     # 可抽象：状态推进
  skills/
    agent-guard/
      scripts/
        validate_guard_profile.py          # 守卫画像校验器，新增全局命令守卫点校验
  assets/
    templates/
      guard-profile/
        minimal/
          global-command-guards.yaml       # 新增：全局命令守卫点模板
```

说明：`core.py` 当前仍是主要实现文件。实现阶段可以先抽出本变更必须共享的能力，不要求一次性完成全部目录拆分。

#### 项目级静态配置目录

```text
.agents/
  guards/
    <profile_id>/
      GUARD-MANIFEST.yaml                  # 守卫画像元数据
      target-model.yaml                    # 被守卫对象模型
      activation-model.yaml                # 激活方式
      observation-model.yaml               # 观察输入模型
      execution-model.yaml                 # 执行和权限模型
      state-machine.yaml                   # 守卫实例状态机
      guard-points.yaml                    # 流程型守卫点
      artifacts.yaml                       # 产物定义
      global-command-guards.yaml           # 新增：静态全局命令守卫点
      brief-template.md                    # 守卫简报模板
      validation-plan.md                   # 守卫画像验证计划
```

`global-command-guards.yaml` 单独成文件，因为它表达“命令边界规则”，不是守卫实例状态，也不是流程型 Guard Point。

#### 项目级运行时动态目录

```text
.local/
  guard/
    audit/                                 # 审计记录；所有 allow / deny / ask 统一写入
    session-observations/                  # 会话观察输入
    session-focus/                         # 会话焦点绑定
    state/                                 # 守卫实例状态；全局命令守卫点不得写入这里
    latest/                                # 最新守卫简报和注入记录
    overrides/                             # 人工覆盖记录
    injections/                            # 注入记录
    evidence/
      <source_scope>/
        <profile_id>/
          <guard_id>/
            <context_key>/
              evidence.json                # 全局命令守卫点或外部流程生成的放行证据
```

等价展开：

```text
.local/guard/evidence/project/<profile_id>/<guard_id>/<context_key>/evidence.json
.local/guard/evidence/user/<profile_id>/<guard_id>/<context_key>/evidence.json
```

`source_scope/profile_id/guard_id` 用于避免多个画像或用户级/项目级同名规则写到同一路径。

原有运行时目录中其他部分保持：

```text
.local/
  guard/
    audit/
    session-observations/
    session-focus/
    state/
    latest/
    overrides/
    injections/
    cache/
```

项目级动态文件继续集中在 `.local/guard`，避免污染静态 profile。项目级全局命令守卫点可读取 `.local/guard/evidence/...`，但不得把自己的运行状态混入 `.local/guard/state/...`。

#### 用户级等价目录

```text
~/.agents/
  guards/<profile_id>/                     # 用户级静态守卫画像
  guard/
    audit/
    session-observations/
    session-focus/
    state/
    latest/
    overrides/
    injections/
    evidence/
      <source_scope>/
        <profile_id>/
          <guard_id>/
            <context_key>/
              evidence.json
    cache/
```

用户级目录语义与项目级一致，只是作用域从当前项目变为当前用户。它只在显式用户作用域运行态使用；用户级安装或用户级 Guard Profile 本身不必然使用这里。项目相关命令即使命中用户级静态规则，默认动态证据和审计仍写项目 `.local/guard`。

## 风险与取舍

- Shell 命令解析不可能完全可靠。第一版只承诺覆盖配置模式和测试覆盖的命令形态，包括 Windows PowerShell 包装 Git Bash。
- 失败策略必须明确。命令明确命中受保护边界但缺少必需捕获值时，必须 fail-closed（拒绝），不能静默放行。
- 全局命令守卫点不依赖会话焦点，因此审计必须记录匹配的有效守卫 ID、工具名、命令、捕获值和失败检查详情。
- 多来源规则是叠加约束，可能让一个命令被多个规则同时拒绝。拒绝输出必须列清楚所有失败守卫，避免主 agent 不知道要补哪份证据。
- evidence 路径必须包含 source scope、profile id、guard id 或等价身份字段，避免不同画像同名规则覆盖彼此证据。
- 当前 change id 仍是 `add-guard-gate-binding`，与新目标名称不完全一致。为避免目录迁移噪音，本变更暂不改名；文档明确 Gate Binding 是废弃方向。

## 测试策略

- 校验器测试：有效配置、缺少命令模式、缺少证据路径、不支持谓词、非法 `value_from`、缺少必需捕获值。
- 命令匹配测试：普通命令、Comet 风格命令 fixture、PowerShell 包装 Git Bash。
- 多来源测试：多个项目级 profile、用户级 + 项目级 profile 同时贡献规则、跨来源同名 `guard_id` 不冲突。
- 运行时测试：无会话焦点仍执行全局命令守卫点、证据缺失、证据过期、证据通过、审计字段完整、多个匹配规则任一失败则拒绝。
- 回归测试：无全局命令守卫点匹配时，现有 Session Focus permission 行为不变；全局守卫允许后，会话焦点仍可拒绝。

## 迁移计划

1. 扩展校验器和模板，支持 `global-command-guards.yaml`，并校验单文件内 guard id 唯一。
2. 抽象命令上下文、命令匹配、JSON 检查等共享能力。
3. 新增全局命令守卫收集器，收集项目级和用户级所有 `global-command-guards.yaml`。
4. 在 PreToolUse 入口评估有效全局命令守卫集，并保持会话焦点路径兼容。
5. 增加通用测试、Comet 风格配置 fixture、多来源叠加测试。
6. 更新 Agent Guard 文档，解释会话焦点守卫、全局命令守卫点、多来源规则叠加的差异。

## 待外部变更确认

- Comet review-pass evidence 的最终路径和内容格式属于 `add-comet-agent-review-gate`。
- 本变更只定义通用模板解析、JSON 检查和命令边界拦截能力。
