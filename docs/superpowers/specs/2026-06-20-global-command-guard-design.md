---
comet_change: add-guard-gate-binding
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-19-add-guard-gate-binding
status: final
---

# 全局命令守卫点设计

## 背景

当前 Agent Guard（代理守卫）主要通过 Session Focus（会话焦点）和 Guard Instance（守卫实例）约束流程。这适合“当前会话正在推进某个守卫流程”的情况，但本需求表达的是另一类边界：

> 只要主 agent 准备执行某个受保护命令，就必须先满足项目级规则。

Comet verify（Comet 验证）前必须完成 review 是第一个用例，但设计不能写死 Comet。最终能力应能守卫任意配置出来的命令点，例如发布、部署、归档、清理或审批后执行。

## 最终方案

新增 Global Command Guard（全局命令守卫点）。它由 Guard Profile（守卫画像）通过 `global-command-guards.yaml` 贡献规则，由 Agent Guard 的 PreToolUse（工具使用前）hook 执行。

执行流程：

1. 主 agent 准备执行 shell 命令。
2. Agent Guard 从工具 envelope（信封）中提取工具名和命令文本。
3. Runtime（运行时）收集所有项目级和用户级 `global-command-guards.yaml`。
4. Runtime 为每条规则生成 effective guard id（有效守卫 ID）：`<source_scope>:<profile_id>:<guard_id>`。
5. Runtime 形成 Effective Global Command Guard Set（有效全局命令守卫集）。
6. Runtime 用配置的 command pattern（命令模式）匹配命令。
7. 命中后提取 named capture（命名捕获），例如 `change`、`tag`、`environment`。
8. Runtime 对所有匹配规则解析 evidence path template（证据路径模板）、读取 JSON evidence（JSON 证据），并执行 JSON predicate（JSON 谓词）检查。
9. 任意匹配规则失败时返回 `deny`，命令不得执行。
10. 所有匹配规则都通过后，继续进入现有 Session Focus permission（会话焦点权限）检查。

这意味着守卫调用点在 Agent Guard hook，不在 Comet，也不依赖主 agent 自觉调用。

## 作用域与运行目录

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

具体规则：

- 当前命令或 hook 事件作用于项目时，运行时动态文件写入 `.local/guard`。这包括用户级插件、用户级 Guard Profile 在项目内触发的项目相关事件。
- 会话焦点实例只有在显式以 `scope=user` 激活或创建时，绑定、实例状态、简报和审计才写入 `~/.agents/guard`。
- 全局命令守卫点默认按命令目标选择运行目录：项目命令写 `.local/guard`；用户全局命令才写 `~/.agents/guard`。
- 如果未来配置需要强制用户级运行态，应显式声明类似 `runtime_scope: user` 的字段；不得仅因配置文件来自 `~/.agents/guards` 就自动写用户级运行目录。
- Comet change review 属于项目和 Git HEAD 相关证据，必须使用项目级 `.local/guard`。

因此，当前“Agent Guard 安装/画像都是用户级，但日志在 `.local/guard`”是合理现象：这些日志是项目上下文里的 hook 审计或无会话焦点审计，不是用户全局运行态。

如果未来同时启用项目级和用户级全局命令守卫点，同一个项目命令可分别命中两个来源的规则；但只要它守卫的是项目命令，默认证据和审计仍应落在项目 `.local/guard`，任一规则拒绝都会阻止命令执行。

## 多来源收集模型

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
- 运行时唯一身份是 effective guard id：`<source_scope>:<profile_id>:<guard_id>`。

示例：

```text
project:repo-policy:verify_requires_review
user:personal-safety:verify_requires_review
```

两条规则的 `guard_id` 都是 `verify_requires_review`，但运行时身份不同，不冲突。

## 评估语义

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

## 配置模型

全局命令守卫点使用独立配置文件：

```text
.agents/guards/<profile_id>/global-command-guards.yaml
```

示例形态：

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

Comet 的 review-before-verify 可以作为一个 profile 配置，匹配 Comet verify 相关命令并检查 review-pass 证据。Runtime 不包含 Comet 专用判断。

## 复用和抽象

本变更优先复用 Agent Guard 已有能力，只新增缺失的全局命令边界层。

| 能力 | 处理方式 |
| --- | --- |
| 命令提取 | 复用现有 `command_from_envelope` / `tool_name_from_envelope`。 |
| 审计和运行时根目录 | 复用现有 `write_audit` / `runtime_root`。 |
| 命令匹配 | 从现有会话焦点权限匹配中抽象共享层。 |
| JSON 谓词 | 从 `json_artifact` 检查中抽象共享 JSON 检查器。 |
| 校验器输出 | 复用 `ValidationIssue` 风格。 |
| 全局命令守卫配置 | 新增 `global-command-guards.yaml`。 |
| 命名捕获和上下文值 | 新增 command context（命令上下文）能力。 |
| 多来源收集 | 新增全局命令守卫收集器，生成有效全局命令守卫集。 |
| 有效守卫 ID | 新增 `<source_scope>:<profile_id>:<guard_id>` 规则身份。 |

实现上不要求一次性大拆 `core.py`。可以先抽出本变更必须共享的命令上下文、命令匹配和 JSON 检查能力，再逐步拆出 `paths.py`、`audit.py`、`session_focus.py` 等文件。

## 目录设计

### 插件源码

```text
plugins/agent-guard/
  scripts/
    hook_router.py
    guard_runtime/
      __init__.py
      cli.py
      core.py
      command_context.py
      command_matcher.py
      json_checks.py
      global_command_guards.py
      paths.py
      audit.py
      session_focus.py
      instances.py
      state_machine.py
  skills/
    agent-guard/
      scripts/
        validate_guard_profile.py
  assets/
    templates/
      guard-profile/
        minimal/
          global-command-guards.yaml
```

语义：

- `guard_runtime/`：运行时能力目录。
- `command_context.py`：构建命令上下文，处理工具名、命令文本、捕获值、`git_head`。
- `command_matcher.py`：处理命令模式、命名捕获和前缀匹配。
- `json_checks.py`：集中 JSON 字段读取和谓词评估。
- `global_command_guards.py`：全局命令守卫收集、匹配、评估。
- `validate_guard_profile.py`：校验静态配置。
- `global-command-guards.yaml`：全局命令守卫点模板。

### 项目级静态配置

```text
.agents/
  guards/
    <profile_id>/
      GUARD-MANIFEST.yaml
      target-model.yaml
      activation-model.yaml
      observation-model.yaml
      execution-model.yaml
      state-machine.yaml
      guard-points.yaml
      artifacts.yaml
      global-command-guards.yaml
      brief-template.md
      validation-plan.md
```

语义：

- `.agents/guards/<profile_id>/`：项目级静态守卫画像。
- `guard-points.yaml`：流程型守卫点。
- `global-command-guards.yaml`：静态命令边界规则。
- `state-machine.yaml`：守卫实例流程状态。
- `artifacts.yaml`：守卫产物定义。

### 项目级运行时动态文件

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
    evidence/
      <source_scope>/
        <profile_id>/
          <guard_id>/
            <context_key>/
              evidence.json
    cache/
```

语义：

- `.local/guard/`：项目级运行时动态根目录。
- `audit/`：所有 allow / deny / ask 审计记录。
- `session-observations/`：会话观察输入。
- `session-focus/`：会话焦点绑定。
- `state/`：守卫实例状态；全局命令守卫点不得写这里。
- `latest/`：最新守卫简报和注入记录。
- `overrides/`：人工覆盖记录。
- `injections/`：注入记录。
- `evidence/`：全局命令守卫点或外部流程生成的放行证据。
- `cache/`：可重建缓存。

evidence 路径必须包含 source scope、profile id、guard id 或等价身份字段，避免多个画像或用户级/项目级同名规则写到同一路径。

### 用户级等价目录

```text
~/.agents/
  guards/<profile_id>/
  guard/
    audit/
    session-observations/
    session-focus/
    state/
    latest/
    overrides/
    injections/
    evidence/
    cache/
```

用户级目录语义与项目级一致，只是作用域从当前项目变为当前用户。它只在显式用户作用域运行态使用；用户级安装或用户级 Guard Profile 本身不必然使用这里。项目相关命令即使命中用户级静态规则，默认动态证据和审计仍写项目 `.local/guard`。

## 错误输出与审计

全局命令守卫点拒绝命令时返回机器可读输出：

```json
{
  "status": "deny",
  "reason": "global_command_guard_required",
  "next": "produce_required_evidence",
  "suggestion": "先生成当前命令对应的通过证据。",
  "matched_guard_ids": [
    "project:release-policy:protected_command_requires_evidence"
  ],
  "failing_guards": [
    {
      "effective_guard_id": "project:release-policy:protected_command_requires_evidence",
      "reason": "evidence_missing",
      "evidence_path": ".local/guard/evidence/project/release-policy/protected_command_requires_evidence/v1.2.3/evidence.json"
    }
  ],
  "captures": {
    "tag": "v1.2.3"
  },
  "audit_path": ".local/guard/audit/<id>.json"
}
```

审计记录必须包含工具名、命令、匹配的有效守卫 ID、捕获值、证据路径和失败检查详情。

## 测试策略

- 校验器测试：有效配置、缺少命令模式、缺少证据路径、不支持 JSON 谓词、非法 `value_from`、缺少必需捕获值。
- 命令匹配测试：普通命令、Comet 风格命令 fixture、PowerShell 包装 Git Bash。
- 多来源测试：多个项目级 profile、用户级 + 项目级 profile 同时贡献规则、跨来源同名 `guard_id` 不冲突。
- 运行时测试：无会话焦点仍执行全局命令守卫点、证据缺失、证据过期、证据通过、审计字段完整、多个匹配规则任一失败则拒绝。
- 回归测试：未命中全局命令守卫点时会话焦点权限不变；全局命令守卫点允许后，会话焦点仍可拒绝。

## 风险

第一，shell 命令解析不能过度承诺。实现只支持配置模式和测试覆盖的命令形态。

第二，失败策略必须保守。命令明确命中受保护边界但缺少必需捕获值时，必须拒绝。

第三，不能把全局命令守卫点变成第二套流程引擎。它只做命令边界检查；流程状态仍由会话焦点和守卫实例负责。

第四，多来源规则是叠加约束，可能让一个命令被多个规则同时拒绝。拒绝输出必须列清楚所有失败守卫，避免主 agent 不知道要补哪份证据。

## Spec Patch

已回写 OpenSpec delta：

- `proposal.md`：目标改为通用全局命令守卫点。
- `design.md`：补充最终方案、多来源收集、叠加评估、复用/抽象边界、完整目录设计。
- `tasks.md`：改为全局命令守卫点实施任务，加入多来源和同名规则测试。
- `specs/agent-guard-plugin-runtime/spec.md`：新增配置目录、多来源收集、命令上下文、共享检查器、证据检查等要求。
