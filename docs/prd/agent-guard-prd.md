# agent-guard PRD

状态：草案

## 问题陈述

用户希望把“agent 应该怎么执行”和“如何证明 agent 严格执行”彻底解耦。

原始设计只关注“技能守卫”：给某个目标 Skill 生成旁路守卫层。经过讨论后，范围需要扩大为“Agent 守卫”：不只守卫 Skill，也能守卫用户提出的任意流程、节点、任务、技能使用方式或执行约束。

这带来新的要求：

- 守卫对象不能再假设一定是 Skill。
- 守卫配置目录不能再用 `<skill-id>` 作为唯一结构。
- 抽象模型要能描述技能、流程、节点、命令、产物生命周期、会话行为和人工约定。
- `agent-guard` 需要先通过问答式调研提炼“被守卫对象”的模型，再生成守卫。
- 生成后的守卫系统仍然必须和目标对象解耦。
- 生成后的项目级守卫系统仍然必须可以脱离用户级 `agent-guard` 独立运行。
- PRD 必须全中文表达，并保留详细技术实现方案。

当前常见问题是：流程说明、技能说明、执行规范、状态、证据、检查、阻断逻辑混在一起。这样会导致：

- 目标 Skill 或流程说明一旦更新，守卫逻辑容易被覆盖。
- 守卫逻辑只能服务一个固定流程，难以复用。
- 多个 agent、多个工作树、多个任务并行时，状态容易串扰。
- 守卫迁移必须修改目标对象，导致耦合和回滚成本上升。
- Codex 与 Claude 需要复用同一套用户级 Skill，但两者默认 Skill 读取目录不同，需要稳定安装方案。

因此需要创建一个用户级通用 Skill：`agent-guard`。它的职责是调研、生成、安装和维护“Agent 守卫系统”，而不是只给某个 Skill 做专用补丁。

经过进一步讨论，第一版必须同时满足两个约束：

- MVP 先落在通用 Guard Profile（守卫画像）契约、最小样例和运行时闭环上，不强制绑定某个具体项目流程或 Skill。
- 抽象和目录结构仍要支持原始设计中的任意守卫对象，不把 PR 流程、Skill 或某个仓库形态写死进 Runtime。

## 方案

创建一个独立维护的用户级 Skill 源码仓库：`my-agent-skills`。

在该仓库中维护 `agent-guard`。`agent-guard` 是“守卫生成器”和“守卫维护工具”，不是项目日常运行时。

`agent-guard` 的用户入口优先是 Codex Skill 显式触发。用户可以通过 `/skills` 选择 `agent-guard`，也可以在提示中使用 `$agent-guard`，或使用“用 agent-guard 守护某个画像”这类明确自然语言。无论哪种方式，都必须被解析为结构化激活请求，例如：

```yaml
action: activate_guard
guard_profile_id: minimal-sample
scope: current_context
```

`agent-guard` 不修改被守卫对象，也不要求目标 Skill 或目标流程增加入口命令。显式激活后，Guard Runtime 必须根据目标 Guard Profile 的 Subject Resolver 先匹配现有守卫实例；没有匹配到时才创建新的守卫实例。

`agent-guard` 的核心能力：

- 使用问答式调研方法提炼被守卫对象。
- 支持守卫技能、流程、节点、命令、产物生命周期、会话行为和一次性用户任务。
- 生成项目级通用 Guard Runtime。
- 生成 Guard Profile。
- 生成状态机、守卫点、产物类别、hook 绑定和验证计划。
- 安装或更新 hook。
- 支持显式激活守卫实例。
- 支持动态注入 Guard Brief，让 agent 在执行过程中知道当前状态和下一步要求。
- 按单个守卫点逐步迁移。
- 支持状态权限 `allow`、`ask`、`deny`。
- 给出现有产物的所有权建议。
- 升级已生成的 Guard Runtime 和 Guard Profile。

生成后的守卫系统分为两部分：

- Guard Runtime：项目级通用守卫运行时，只负责执行通用机制。
- Guard Profile：某个具体守卫对象的旁路配置，描述要守卫什么、如何观察、如何判断、何时阻断、如何记录。

被守卫对象保持原样。它可以是 Skill，也可以不是 Skill。MVP 通过 Codex 生命周期 hook、Git hook、状态读取、会话事件和人工确认结果来观察 agent 执行过程；命令包装器、文件 watcher、Claude 生命周期 hook 和外部 API 观察保留为后续扩展。

Codex 当前没有稳定的 Skill 启动或 Skill 选择生命周期事件，因此本方案不能依赖“检测 Codex 是否读取了某个 Skill 文件”来创建守卫实例。PR 流程类守卫通过 `agent-guard` 显式激活、`UserPromptSubmit`、`SubagentStart`、`SubagentStop`、`PreToolUse`、`PostToolUse` 和 Git hook 观察流程，而不是修改目标 PR Skill。

## 目标

- 创建用户级 `agent-guard` Skill。
- 创建 `my-agent-skills` 源码仓库初始化方案。
- 支持生成项目级 Guard Runtime。
- 支持生成通用 Guard Profile。
- 支持守卫任意 agent 执行对象，而不仅是 Skill。
- 支持通过问答式调研提炼模型。
- 支持状态机、守卫点、产物、hook、快照、交接包。
- 支持多工作树、多 agent、多任务并发隔离。
- 支持生成后的守卫系统独立运行。
- 保持初始化简单够用，不引入重型 CI 和完整测试体系。

## MVP 范围

MVP 以通用 `minimal-sample` Guard Profile（守卫画像）跑通生成、初始化、激活、事件运行、审计和 Guard Brief（守卫简报）闭环。具体项目流程或 Skill 的业务画像通过后续调研生成，不作为 MVP 必需内置样例。Runtime、目录结构和 Profile 模型必须保持通用，不把 PR 流程、Skill 或某个仓库形态写死进 Runtime。

MVP 必须包含：

- 用户级 `agent-guard` Skill 的显式激活入口。
- 项目级 Guard Runtime。
- 项目级 Guard Profile。
- Codex 生命周期 hook 适配。
- Git hook 适配。
- 标准事件 envelope。
- Subject Resolver。
- 状态机执行。
- 守卫点执行。
- 状态权限 `allow/ask/deny`。
- 动态 Guard Brief 注入。
- 运行审计。
- 最小人工覆盖机制。
- 基于 `subject-key-hash` 的运行状态目录。

MVP 暂不包含：

- Claude 生命周期 hook。
- 命令包装器作为主要阻断入口。
- 文件 watcher。
- 外部 API 主动轮询。
- 自动识别 Codex 是否读取某个 Skill 文件。
- 自动迁移既有产物所有权。
- 全局多 Profile 裁决器。
- 重型 CI 和 verify fast/full 命令体系。源码仓库可以保留最小自测；项目初始化输出不得生成完整测试目录。

## 非目标

- 不重写任何被守卫对象。
- 不要求目标 Skill 或目标流程主动调用守卫 API。
- 不自动迁移既有产物所有权。
- 不在通用方案中写入任何具体业务流程规则。
- 不默认生成 `deny` 权限规则；当前阶段 `deny` 通过 Guard Profile（守卫画像）的 `states[].permissions` 显式声明和维护。
- 不把 `repo + worktree + branch` 写成通用 Subject Key 默认规则。
- 不依赖 Codex 的 Skill 读取行为来识别流程启动。
- 不在 MVP 中支持 Claude 生命周期 hook。
- 不把命令包装器作为 MVP 的主要阻断入口。
- 不在初始化阶段创建 GitHub Actions。
- 不在目标项目初始化阶段创建完整测试目录。
- 不在初始化阶段创建 verify fast/full 命令体系。
- 不把用户级 `agent-guard` 作为项目运行时依赖。

## 用户故事

1. 作为用户，我希望 `agent-guard` 能守卫任意 agent 执行过程，以便不局限于某个 Skill。

2. 作为用户，我希望 `agent-guard` 能先问答式调研我的流程，以便把模糊要求转成清晰守卫模型。

3. 作为用户，我希望可以守卫一个 Skill，以便 Skill 更新时守卫能力不丢失。

4. 作为用户，我希望可以守卫一个流程，以便 agent 必须按流程顺序执行。

5. 作为用户，我希望可以守卫一个节点，以便关键节点必须满足前置条件才能继续。

6. 作为用户，我希望可以守卫一次临时任务，以便临时约定也能被记录和检查。

7. 作为用户，我希望守卫逻辑不修改目标对象，以便目标对象可以独立更新。

8. 作为用户，我希望生成后的项目级守卫能独立运行，以便 clone 项目后不依赖用户级生成器。

9. 作为用户，我希望守卫配置能被 Git 跟踪，以便团队或多个工作树能共享同一套守卫能力。

10. 作为用户，我希望非项目级守卫也有用户级存放位置，以便守卫个人通用流程。

11. 作为维护者，我希望 `my-agent-skills` 管理用户级 Skill 源码，以便通过 GitHub PR 维护个人 Skill。

12. 作为维护者，我希望仓库初始化保持简单，以便先把核心能力跑通。

13. 作为 Codex 用户，我希望 Codex 能直接读取用户级 `.agents` Skill，以便少维护一份副本。

14. 作为 Claude 用户，我希望 Claude 通过 Junction 复用同一份 Skill，以便 Codex 和 Claude 不漂移。

15. 作为 agent，我希望 Guard Profile 明确守卫对象类型，以便同一套运行时能处理技能、流程、节点和任务。

16. 作为 agent，我希望 Guard Profile 明确观察信号，以便知道从哪里判断执行进展。

17. 作为 agent，我希望 Guard Profile 明确状态机，以便知道哪些状态转换被允许。

18. 作为 agent，我希望 Guard Profile 明确守卫点，以便知道在哪些事件上执行校验。

19. 作为 agent，我希望 Guard Profile 明确产物类别，以便知道哪些文件、记录或外部结果需要读取或生成。

20. 作为 agent，我希望 Guard Runtime 只包含通用执行能力，以便它不会和某个具体流程耦合。

21. 作为 agent，我希望 Guard Class 和 Guard Instance 分开，以便复用守卫类型，同时隔离具体运行。

22. 作为 agent，我希望 Artifact Class 和 Artifact Instance 分开，以便复用产物模型，同时记录具体产物。

23. 作为 agent，我希望状态和运行审计分开，以便既能知道当前状态，也能追溯本次运行。

24. 作为项目维护者，我希望每个守卫点能独立启用，以便逐步迁移，降低风险。

25. 作为项目维护者，我希望每个守卫点能独立回滚，以便某个守卫点出错时不影响全部守卫。

26. 作为项目维护者，我希望会拒绝操作的状态权限只在 Guard Profile（守卫画像）的 `states[].permissions` 中显式声明，以便初始化和 hook 安装不会隐式改变拒绝规则。

27. 作为项目维护者，我希望 hook 安装必须显式授权，以便不会悄悄改变项目行为。

28. 作为项目维护者，我希望运行状态按工作树和任务隔离，以便多个 agent 并发运行不互相覆盖。

29. 作为项目维护者，我希望守卫优先注册已有产物，以便不强行改变现有流程。

30. 作为项目维护者，我希望守卫能生成自己的产物，以便保存快照、审计和交接信息。

31. 作为项目维护者，我希望 `agent-guard` 给出产物迁移建议，以便由我决定是否迁移。

32. 作为未来维护者，我希望 ADR 记录关键架构决策，以便理解为什么这样拆分。

33. 作为未来维护者，我希望术语表全中文，以便减少概念歧义。

34. 作为未来维护者，我希望技术实现方案详细保留，以便后续 agent 可以直接实现。

35. 作为用户，我希望可以通过 `/skills`、`$agent-guard` 或“用 agent-guard 守护某个画像”的明确表达激活守卫，以便不需要修改目标 Skill。

36. 作为用户，我希望显式激活时优先匹配现有守卫实例，以便同一任务、分支或外部对象不会重复创建状态。

37. 作为用户，我希望 Guard Profile 自己定义 Subject Resolver，以便不同守卫对象可以使用不同身份字段。

38. 作为用户，我希望 Runtime 只提供上下文而不猜测守卫实例，以便实例匹配可审计、可配置、可调试。

39. 作为 agent，我希望每次守卫状态变化后都收到最新 Guard Brief，以便知道当前状态、允许下一步、禁止下一步和缺失产物。

40. 作为 agent，我希望 Guard Brief 被去重且保持短格式，以便不因为重复注入浪费上下文或造成混乱。

41. 作为项目维护者，我希望主 agent（主代理）事件无法解析明确守卫实例时不返回 `deny` 但必须审计，以便既避免误伤，也能 debug 守卫配置。

42. 作为项目维护者，我希望已解析实例但无匹配状态转换时默认忽略，以便无关 hook 事件不会制造噪音。

43. 作为项目维护者，我希望同一实例内多转换匹配被视为 Profile 错误，以便状态机不会在歧义下推进。

44. 作为项目维护者，我希望 `deny` 结果只在明确守卫实例内部生效，以便多个 Guard Profile 或多个实例不会互相连坐。

45. 作为项目维护者，我希望人工覆盖默认关闭且有过期时间，以便临时例外可审计且不会变成永久后门。

46. 作为 Codex 用户，我希望 MVP 先兼容 Codex 生命周期 hook，以便先把主要交互路径跑通，再扩展 Claude。

## 核心抽象

### Agent 守卫

Agent 守卫是对 agent 执行过程的旁路治理机制。它不接管 agent 的工作，也不修改被守卫对象，而是通过外部事件、产物、状态和 hook 判断 agent 是否按约定执行。

### 守卫对象

守卫对象是被守卫的目标。它不再限制为 Skill。

守卫对象类型包括：

- 技能：一个已有 Skill。
- 流程：一组有顺序、有状态、有产物的步骤。
- 节点：流程中的关键检查点或动作。
- 命令：某个 CLI 命令或脚本调用。
- 产物生命周期：某类文件、记录、报告或证据的生成和更新过程。
- 会话行为：agent 在对话或任务中的执行约定。
- 临时任务：用户在一次会话中定义的临时执行要求。

### 守卫画像

守卫画像是某个守卫对象的旁路配置。它描述这个对象是什么、如何观察、有哪些状态、有哪些守卫点、哪些产物需要管理、哪些 hook 会触发运行。

目录名使用 `<guard-profile-id>`，不再使用 `<skill-id>`。

Guard Profile 必须定义：

- 守卫对象。
- Subject Resolver。
- 状态机。
- 守卫点。
- 产物类别。
- hook 绑定。
- 守卫简报内容。
- 结束条件。
- 权限和覆盖规则。

Guard Runtime 不得在自身代码中写入具体业务流程规则，也不得替 Guard Profile 猜测 Subject Key。

### 守卫实例

守卫实例是某个 Guard Profile 在某个具体 Subject 上的运行上下文。一个 Guard Profile 可以同时有多个守卫实例。

权限、错误和允许结果只适用于同一个守卫实例内部，不默认跨 Guard Profile 或跨守卫实例做全局合并。`deny` 结果必须绑定到明确守卫实例。

### 守卫激活命令

守卫激活命令是 `agent-guard` 自己提供的显式声明入口，用来让用户或 agent 声明“本次会话或任务需要某个守卫画像”。

MVP 优先通过 Codex Skill 显式触发：

- 通过 `/skills` 选择 `agent-guard`。
- 在提示中使用 `$agent-guard`。
- 使用“用 agent-guard 守护某个画像”这类明确表达。

激活请求必须被解析为结构化输入。Runtime 收到激活请求后，必须根据 Guard Profile 的 Subject Resolver 先匹配现有守卫实例；没有匹配到时才创建新实例。

### Subject Resolver

Subject Resolver 是 Guard Profile 中负责解析守卫实例身份的规则。Runtime 只提供当前上下文，例如 repo、worktree、branch、PR 编号、会话 ID、任务 ID、目标对象 ID、外部系统 ID 和 hook payload 中的标准字段。

不同 Guard Profile 可以使用不同身份策略。例如 PR 流程可以选择 `repo + PR 编号`，也可以选择 `repo + worktree + branch`；外部审批流程可以选择 `external_system_id + request_id`。这些都是具体 Profile 的选择，不是 Runtime 默认。

### 守卫简报

守卫简报是注入给 agent 的短文本或结构化摘要。它用于告诉 agent 当前守卫状态、允许下一步、禁止下一步、缺失产物、最近拒绝或失败原因和审计位置。

守卫简报用于提高执行效率，不替代 Hook（钩子）对 `deny` 结果的执行。

### 目标模型

目标模型描述被守卫对象本身：

- 对象类型。
- 对象名称。
- 对象来源。
- 对象边界。
- 用户目标。
- 允许的执行方式。
- 禁止的执行方式。
- 关键节点。
- 关键产物。
- 可观察信号。

### 执行模型

执行模型描述 agent 应如何推进：

- 状态。
- 节点。
- 转换。
- 前置条件。
- 后置条件。
- 可跳过条件。
- 异常分支。
- 人工确认点。

### 观察模型

观察模型描述守卫如何从外部判断 agent 做了什么：

- hook 事件。
- Git 状态。
- 文件变化。
- 命令输出。
- JSON 状态文件。
- 外部 API 查询结果。
- 对话摘要。
- 人工确认记录。

### 状态机

状态机描述允许的状态和状态转换。状态机属于守卫层，不属于被守卫对象。

运行时收到事件后，必须先匹配状态转换，再执行转换上的守卫点。只有守卫点全部通过，状态才能推进。

### 状态权限管理

当前阶段不提供独立的 Dynamic Permission Management（动态权限管理）入口。状态权限 `allow`、`ask`、`deny` 直接由 Guard Profile（守卫画像）的 `states[].permissions` 管理。

当前阶段的边界：

- `states[].permissions` 是 Runtime（运行时）读取和执行状态权限的权威配置。
- 权限规则的创建、更新和删除通过编辑 Guard Profile（守卫画像）完成。
- 权限规则变更的审计和回滚依赖 Git。
- 独立 Dynamic Permission Management（动态权限管理）入口是未来扩展，不属于当前验收范围。

项目级初始化、用户级初始化和 hook 安装都不得隐式创建、修改或授权 `deny` 规则。Hook（钩子）只把事件交给 Runtime（运行时），并按 Runtime（运行时）返回结果执行；它不拥有单独的阻断授权开关。

### 守卫点

守卫点是在某个事件或状态转换上执行的校验。守卫点失败只决定状态是否推进；工具操作是否拒绝由状态权限决定。

守卫点必须可独立启用、独立验证、独立回滚。

### 产物

产物可以是文件、日志、JSON、外部记录、快照、交接包或人工确认记录。

产物按所有权分为：

- 外部引用产物：由被守卫对象或原流程拥有，守卫只读取和验证。
- 守卫自有产物：由守卫生成和维护。
- 迁移候选产物：当前不属于守卫，但本质上更像守卫证据，需要由用户决定是否迁移。

## 目录结构

### `my-agent-skills` 源码仓库

初始化保持简单够用：

```text
my-agent-skills/
├── AGENTS.md
├── CLAUDE.md
├── .gitignore
├── .gitattributes
├── .agents/
│   └── skills/
│       └── agent-guard/
│           ├── SKILL.md
│           ├── agents/
│           │   └── openai.yaml
│           ├── references/
│           │   ├── architecture.md
│           │   ├── terminology.md
│           │   ├── extraction-method.md
│           │   ├── guard-profile.md
│           │   ├── runtime-contract.md
│           │   ├── hook-contract.md
│           │   ├── subject-resolution.md
│           │   ├── guard-injection.md
│           │   └── codex-claude-compat.md
│           ├── assets/
│           │   └── templates/
│           │       ├── guard-runtime/
│           │       ├── guard-profile/
│           │       ├── user-guard-profile/
│           │       ├── hook-bindings/
│           │       ├── codex-hooks/
│           │       ├── git-hooks/
│           │       ├── guard-brief/
│           │       └── validation-plan/
│           └── scripts/
│               ├── init_project_guard.py
│               ├── init_user_guard.py
│               ├── extract_guard_model.py
│               ├── activate_guard.py
│               ├── run_guard_event.py
│               ├── render_guard_brief.py
│               ├── validate_guard_profile.py
│               ├── install_hooks.py
│               └── upgrade_guard_runtime.py
├── docs/
│   ├── rules/
│   │   └── index.md
│   └── adr/
│       ├── index.md
│       └── 0001-agent-guard-architecture.md
└── scripts/
    └── install/
        ├── install_user_skill.ps1
        ├── sync_claude_junction.ps1
        └── verify_install.py
```

不初始化以下内容：

- GitHub Actions。
- verify fast/full。
- CODEOWNERS。
- tests 目录。
- githooks。
- 复杂发布系统。

这些后续有实际维护压力时再增加。

### 用户级安装目录

`agent-guard` 安装到：

```text
C:\Users\liuli\.agents\skills\agent-guard\
```

Claude 通过 Junction 复用：

```text
C:\Users\liuli\.claude\skills\agent-guard
  -> C:\Users\liuli\.agents\skills\agent-guard
```

Codex 直接读取用户级 `.agents` Skill。

### 项目级守卫目录

项目级守卫进入目标项目 Git：

```text
目标项目/
└── .agents/
    ├── guard-runtime/
    │   ├── VERSION
    │   ├── RUNTIME-MANIFEST.yaml
    │   ├── requirements.txt
    │   ├── guard_runner.py
    │   ├── engine/
    │   ├── adapters/
    │   ├── checks/
    │   └── schemas/
    └── guards/
        └── <guard-profile-id>/
            ├── GUARD-MANIFEST.yaml
            ├── target-model.yaml
            ├── execution-model.yaml
            ├── observation-model.yaml
            ├── state-machine.yaml
            ├── artifact-classes/
            ├── guard-points/
            ├── hook-bindings/
            ├── brief/
            ├── snapshot-classes/
            ├── concurrency.yaml
            ├── migration-plan.md
            └── validation-plan.md
```

关键变化：

- 不再使用 `.agents/guards/<skill-id>/`。
- 改为 `.agents/guards/<guard-profile-id>/`。
- 通过 `target-model.yaml` 说明这个画像守卫的是什么。
- 同一个 Skill 可以有多个 Guard Profile。
- 一个 Guard Profile 也可以守卫非 Skill 对象。

### 用户级守卫目录

如果守卫对象不是某个项目内的对象，可以放到用户级守卫目录：

```text
C:\Users\liuli\.agents\guards\
└── <guard-profile-id>/
    ├── GUARD-MANIFEST.yaml
    ├── target-model.yaml
    ├── execution-model.yaml
    ├── observation-model.yaml
    ├── state-machine.yaml
    ├── artifact-classes/
    ├── guard-points/
    ├── hook-bindings/
    └── validation-plan.md
```

默认规则：

- 项目相关守卫优先放项目 `.agents/guards/`，进入项目 Git。
- 个人通用守卫放用户级 `.agents/guards/`。
- 可以后续把成熟的用户级守卫模板迁移进 `my-agent-skills` 的模板目录。

### 运行状态目录

运行状态不进 Git：

```text
目标项目/
└── .local/
    └── guard/
        ├── state/
        │   └── <guard-profile-id>/
        │       └── <subject-key-hash>/
        │           └── state.json
        ├── runs/
        │   └── <run-id>/
        │       ├── event.json
        │       ├── result.json
        │       ├── state-before.json
        │       ├── state-after.json
        │       ├── artifacts.json
        │       ├── audit.json
        │       ├── raw-event.json
        │       ├── guard-points.json
        │       └── handoff/
        ├── overrides/
        │   └── <guard-profile-id>/
        │       └── <subject-key-hash>/
        │           └── <guard-point-id>.json
        └── latest/
            └── <guard-profile-id>/
                └── <subject-key-hash>/
                    ├── brief.md
                    └── latest.json
```

用户级守卫运行状态可放到：

```text
C:\Users\liuli\.agents\local\guard\
```

## 运行机制

### 总体链路

```text
外部事件
  -> hook 或适配器捕获
  -> 标准化为 guard event
  -> 调用 Guard Runtime
  -> 加载 Guard Profile
  -> 解析 Guard Instance
  -> 读取当前状态
  -> 匹配状态转换
  -> 执行守卫点
  -> 守卫通过后推进状态
  -> 写入运行审计
  -> 状态变化后生成最新 Guard Brief
  -> 写入快照或交接包
  -> 返回允许、询问、拒绝或错误结果
```

Guard Brief 不由 Runtime 主动推送给 agent。Runtime 只在状态变化后写入 latest brief，后续由可注入的 Codex 生命周期 hook 注入给 agent。

### 事件模型

事件需要包含：

- 事件 ID。
- 事件类型。
- 事件来源。
- 事件时间。
- 当前项目路径。
- 当前工作树路径。
- 当前 agent 标识。
- 当前会话标识。
- 原始事件载荷。
- 标准化后的上下文。

事件来源可以是：

- Codex 生命周期事件。
- Git hook。
- 用户确认。
- 手动运行。

MVP 第一版必须支持的 Codex 生命周期事件：

- `UserPromptSubmit`。
- `PreToolUse`。
- `PostToolUse`。
- `SubagentStart`。
- `SubagentStop`。

MVP 后续扩展的 Codex 生命周期事件：

- `SessionStart`。
- `PreCompact`。
- `Stop`。

MVP 第一版必须支持的 Git hook：

- `pre-push`。

MVP 后续扩展的 Git hook：

- `pre-commit`。

Claude 生命周期事件、命令包装器、文件 watcher 和外部 API 主动观察作为后续扩展。

### 标准事件 envelope

所有 adapter 必须输出统一标准事件 envelope。Guard Profile、状态机和守卫点只能依赖标准事件字段，不直接依赖原始 hook payload。Codex Hook adapter（钩子适配器）不得把完整原始 payload 原样交给 Runtime（运行时）；只能保留工具名、命令、路径、参数字段、上下文和 hook 元数据。Runtime（运行时）的 `raw-event.json` 保存标准事件 envelope，用于审计和 debug。

标准事件至少包含：

- `event_id`。
- `event_type`。
- `source`。
- `timestamp`。
- `guard_profile_id` 或 `profile_ref`。
- `context`。
- `subject`。
- `payload`：只包含白名单后的命令、路径、参数或工具输入摘要。
- `tool`。
- `action`。
- `hook`。
- `raw_event_summary`。

`target_hint` 可以作为可选线索，但不能作为权威身份。最终 Subject Key 必须由 Guard Profile 的 Subject Resolver 计算。

### 守卫实例解析

Runtime 收到事件后，必须先确定是否能解析到明确守卫实例。

规则：

- 主 agent（主代理）事件解析到 0 个实例：不返回 `deny`，但必须写 `no_subject_match` 审计。
- 主 agent（主代理）事件解析到多个实例：不返回 `deny`，但必须写 `ambiguous_subject` 审计。
- Hook（钩子）事件无法解析到唯一实例：不拒绝、不提示、不写审计，按 `no_guard_instance` 忽略。
- 解析到 1 个实例：进入该实例的状态机。

主 agent（主代理）事件的 `no_subject_match` 和 `ambiguous_subject` 审计至少包含原始事件引用、候选 Guard Profile、解析失败原因和修复建议。Hook（钩子）事件的无实例分支按 hook-contract（钩子契约）忽略，不产生审计噪音。

`deny` 结果必须来自明确守卫实例，不能由全局 Runtime 对多个实例做连坐式拒绝。

### Subject 模型

Subject 是一次被守卫的具体执行对象。

Subject Key 是 Subject 的稳定身份键。Subject Key 不由 Runtime 固定生成，而是由 Guard Profile 的 Subject Resolver 定义。

Runtime 需要提供可用上下文字段：

- 守卫画像 ID。
- scope 类型。
- 仓库 ID。
- 工作树路径。
- branch。
- PR 编号。
- agent 标识。
- 会话标识。
- 任务标识。
- 对象类型。
- 对象 ID。
- 执行上下文 ID。
- 外部系统 ID。

Guard Profile 需要声明哪些字段是必需字段、哪些字段是可选隔离字段。`agent_id`、`session_id`、`task_id` 不能作为所有守卫对象的强制字段；它们只能由具体 Profile 决定是否必需。

易变值只记录在状态中，不作为核心身份：

- 当前 commit。
- 当前 diff hash。
- 当前分支快照。
- 当前文件 hash。

这样可以避免同一个长期任务因为 commit 变化而不断生成新 subject。

状态目录不直接使用完整 Subject Key。Runtime 需要计算 `subject-key-hash` 作为路径段，完整 Subject Key 写入 `state.json` 和审计文件，避免 Windows 路径过长或非法字符问题。

### 状态机执行

状态机定义在 `state-machine.yaml`。

运行规则：

- 运行时读取当前状态。
- 只有主 agent（主代理）主动提交 `state_completed` 且 `completed_state_id` 等于当前状态时，才进入状态转换判断。
- Runtime（运行时）根据状态、转换条件、产物和守卫点结果匹配唯一转换。
- `state_completed` 不能用 `payload.*` 选择转换或提供完成证据；agent 必须先按 `artifacts.yaml` 声明的位置写入产物，再提交完成事件。
- 如果没有匹配到转换或匹配到多个转换，视为状态机配置错误，返回 `error`，写运行审计，且不得推进状态。
- Hook（钩子）事件只做权限检查、审计和提示，不推进状态。
- 执行转换绑定的守卫点。
- 只有守卫点全部通过，或失败守卫点都有有效人工覆盖，才写入新状态。
- 守卫点失败且没有有效人工覆盖时，返回 `error/guard_failed`，写运行审计，刷新 Guard Brief（守卫简报），不推进状态。
- 已处于终止状态的守卫实例再次收到 `state_completed` 时，返回 `error/terminal_state_completed`，不推进状态。

### 守卫点执行

守卫点定义在 `guard-points/`。

守卫点至少包含：

- 守卫点 ID。
- 触发事件。
- 适用状态。
- 输入产物。
- 检查逻辑。
- 失败提示。
- 是否允许人工覆盖。
- 覆盖记录要求。

失败守卫点没有有效人工覆盖时，统一返回 `error/guard_failed` 并保持当前状态。

`guard_error` 指守卫点自身运行失败，例如脚本异常、依赖缺失或输入产物读取失败。`guard_error` 按 `error` 处理。

`runtime_error` 指 Guard Runtime 自身错误，例如 Profile 加载失败、状态写入失败或锁获取异常。`runtime_error` 返回 `error`。

### 产物管理

产物类别定义在 `artifact-classes/`。

每类产物至少包含：

- 产物类别 ID。
- 产物名称。
- 产物来源。
- 所有权。
- 存放位置或查询方式。
- 创建规则。
- 更新时间规则。
- 新鲜度规则。
- hash 或版本规则。
- 生产者。
- 消费者。
- 和状态机的关系。

所有权类型：

- 外部引用产物。
- 守卫自有产物。
- 迁移候选产物。

守卫默认只注册和读取既有产物，不自动迁移所有权。

### Hook 绑定

Hook 绑定定义在 `hook-bindings/`。

Hook 绑定只做三件事：

- 捕获外部事件。
- 标准化事件。
- 调用 Guard Runtime。

Hook 绑定不写业务规则。

安装 hook 必须显式授权。Hook 是否拒绝动作由当前 Guard Instance（守卫实例）状态下 `states[].permissions` 的 `deny` 结果决定，没有额外阻断开关。

Hook 绑定由每个 Guard Profile 自己携带。Guard Runtime 只提供通用 adapters，用来把 Codex 或 Git 的原始事件转换为标准事件。

Hook 绑定只声明：

- provider。
- hook event。
- 使用哪个 adapter。
- 如何把标准事件交给 Runtime。

是否拒绝当前动作由 Guard Profile（守卫画像）里的状态权限决定；状态是否推进、失败后如何处理，由 Guard Profile 的状态机和守卫点定义。

### Guard Injection

Guard Injection 是把当前守卫实例的状态、允许动作、禁止动作、缺失产物和下一步建议提前提供给 agent 的机制。它用于提高执行效率，不替代 Codex Hook 或 Git Hook 对 `deny` 结果的执行。

动态注入规则：

- 每次状态变化后，Runtime 必须重新生成最新 Guard Brief。
- Runtime 只写入 latest brief，不主动推送消息给 agent。
- 后续可注入的 Codex hook 读取 latest brief 并注入。
- 只有解析到唯一明确的守卫实例才允许注入。
- 注入内容只能来自 Runtime 生成的最新 Guard Brief。
- 注入前必须校验 `subject-key-hash`、`state_version` 和过期时间。
- 注入必须用 `brief_hash` 按 Codex session 去重。
- 相同 `brief_hash` 不重复注入。
- 简报必须保持固定短格式。

Guard Brief 至少包含：

- Guard Profile。
- Subject。
- 当前状态。
- 允许下一步。
- 禁止下一步。
- 缺失产物。
- 最近拒绝或失败原因。
- 相关审计位置。

Guard Brief 的结构和默认文本由 Runtime 统一生成。Guard Profile 提供状态语义、允许动作、禁止动作、缺失产物、下一步建议和可选文案模板。Runtime 可以做一致性校验，避免简报文案和状态机规则漂移。

### 人工覆盖

MVP 支持最小人工覆盖文件机制，但默认关闭。

只有 Guard Profile 或具体守卫点显式 `allow_override: true` 时才允许覆盖。覆盖必须绑定到具体 Subject 和具体守卫点，不能是全局永久豁免。

覆盖文件建议放在：

```text
.local/guard/overrides/<guard-profile-id>/<subject-key-hash>/<guard-point-id>.json
```

覆盖内容至少包含：

- `decision`。
- `reason`。
- `approved_by`。
- `approved_at`。
- `expires_at`。

使用人工覆盖时，必须写入运行审计。

### 运行审计规则

MVP 只对关键路径写审计：

- 主 agent（主代理）事件无法解析守卫实例。
- 匹配到唯一转换。
- 匹配到多个转换。
- 执行过守卫点。
- 使用人工覆盖。
- 发生 Runtime 错误或锁错误。

已解析到守卫实例但收到非推进事件时，默认不写状态推进审计；`state_completed` 无匹配转换时必须写 error（错误）审计。

每条运行审计至少记录：

- `run_id`。
- 时间。
- hook 来源。
- 事件类型。
- Guard Profile。
- Subject Key。
- `subject-key-hash`。
- 转换前状态。
- 匹配转换。
- 守卫点结果。
- 最终决策。
- 转换后状态。
- 原始事件引用。

### 交接包

交接包是守卫自有产物。

它用于让另一个 agent 接手时快速理解：

- 当前 subject。
- 当前状态。
- 最近事件。
- 最近失败守卫点。
- 已满足条件。
- 未满足条件。
- 需要人工确认的事项。
- 可继续执行的下一步。

交接包默认写入运行审计目录。

## 详细技术实现方案

### `agent-guard` Skill 结构

`SKILL.md` 保持简洁，只包含：

- 什么时候使用 `agent-guard`。
- 总体工作方式。
- 必须先调研再生成。
- 不修改被守卫对象。
- hook 安装必须显式授权；`deny` 权限只能由 Guard Profile（守卫画像）的 `states[].permissions` 显式声明。
- 详细内容的引用路径。

详细文档放入 `references/`：

- `architecture.md`：整体架构。
- `terminology.md`：术语表。
- `extraction-method.md`：问答式提炼方法。
- `guard-profile.md`：Guard Profile 格式。
- `runtime-contract.md`：Guard Runtime 契约。
- `hook-contract.md`：hook 绑定契约。
- `subject-resolution.md`：守卫实例解析规则。
- `guard-injection.md`：动态注入和 Guard Brief 规则。
- `codex-claude-compat.md`：Codex 与 Claude 兼容安装。

模板放入 `assets/templates/`：

- `guard-runtime/`：项目级运行时骨架。
- `guard-profile/`：项目级画像骨架。
- `user-guard-profile/`：用户级画像骨架。
- `hook-bindings/`：hook 绑定模板。
- `codex-hooks/`：Codex 生命周期 hook 模板。
- `git-hooks/`：Git hook 模板。
- `guard-brief/`：守卫简报模板。
- `validation-plan/`：验证计划模板。

### 生成命令

建议 `agent-guard` 脚本提供以下能力：

- `extract_guard_model.py`：根据问答结果生成目标模型草案。
- `activate_guard.py`：根据显式激活请求匹配或创建守卫实例。
- `init_project_guard.py`：在项目中初始化 Guard Runtime 和 Guard Profile。
- `init_user_guard.py`：初始化用户级 Guard Profile。
- `run_guard_event.py`：从标准事件执行一次守卫运行。
- `render_guard_brief.py`：根据当前状态生成最新 Guard Brief。
- `validate_guard_profile.py`：校验 Guard Profile 完整性。
- `install_hooks.py`：按授权安装 hook。
- `upgrade_guard_runtime.py`：升级项目内 Guard Runtime。

这些脚本是给 agent 调用的稳定工具，不要求用户手工记忆所有参数。

### Guard Manifest

`GUARD-MANIFEST.yaml` 是 Guard Profile 入口。

它应包含：

- 画像 ID。
- 画像名称。
- 画像版本。
- 守卫对象引用。
- 运行时版本要求。
- Subject Resolver 路径。
- 激活规则路径。
- 状态机文件路径。
- 观察模型文件路径。
- 守卫点目录。
- 产物类别目录。
- hook 绑定目录。
- 守卫简报目录。
- schema version。
- 文件索引。
- 是否允许人工覆盖。
- 并发配置路径。

### Target Model

`target-model.yaml` 描述被守卫对象。

字段建议：

- `target.id`：对象 ID。
- `target.type`：对象类型。
- `target.name`：对象名称。
- `target.source.kind`：对象来源类型。
- `target.source.ref`：对象引用。
- `target.boundary`：边界说明。
- `target.goal`：用户目标。
- `target.non_goals`：非目标。
- `target.expected_behavior`：期望行为。
- `target.forbidden_behavior`：禁止行为。

对象来源类型可以是：

- skill 文件。
- 文档文件。
- 用户会话总结。
- 命令。
- 外部系统。
- 手工录入。

### Activation Model

`activation-model.yaml` 描述什么时候可以创建或匹配守卫实例。

字段建议：

- `activation.allowed_sources`：允许的激活来源，例如 `agent-guard-skill`、`user_prompt_submit`、`manual`。
- `activation.required_profile_ref`：是否必须明确给出 Guard Profile ID。
- `activation.scope`：激活范围，例如 `current_context`、`project`、`user`、`external`。
- `activation.parse_rules`：如何把用户输入解析为结构化激活请求。
- `activation.on_existing_subject`：命中现有实例时如何处理。
- `activation.on_missing_subject`：没有现有实例时是否允许创建。
- `activation.initial_state`：新实例初始状态。

MVP 中，普通用户话术不能隐式创建强约束实例。只有显式 `agent-guard` 调用，或 Guard Profile 明确允许的 `UserPromptSubmit` 激活规则，才允许创建实例。

### Subject Resolver

`subject-resolver.yaml` 描述如何从当前上下文和标准事件中计算 Subject Key。

字段建议：

- `subject.identity_fields`：组成 Subject Key 的字段。
- `subject.required_fields`：必须存在的字段。
- `subject.optional_fields`：可选隔离字段。
- `subject.context_sources`：可使用的上下文来源。
- `subject.existing_match_policy`：如何匹配现有实例。
- `subject.create_policy`：何时允许创建新实例。
- `subject.ambiguous_policy`：多个实例匹配时的处理。

Runtime 可以提供 repo、worktree、branch、PR 编号、session、task、目标对象、外部系统 ID 等上下文字段，但具体使用哪些字段由 Guard Profile 决定。

### Execution Model

`execution-model.yaml` 描述 agent 应如何执行。

字段建议：

- 节点列表。
- 节点类型。
- 节点前置条件。
- 节点完成条件。
- 节点允许跳过条件。
- 节点失败处理。
- 节点产物。
- 节点可观察信号。
- 人工确认点。
- 每个状态的允许下一步。
- 每个状态的禁止下一步。
- 每个状态的缺失产物说明。
- 每个状态的 Guard Brief 文案字段。

它和状态机不同：

- 执行模型偏“人能理解的流程结构”。
- 状态机偏“运行时可执行的状态转换”。

两者都属于守卫画像，不属于被守卫对象。

### Observation Model

`observation-model.yaml` 描述如何观察 agent 执行。

字段建议：

- 信号 ID。
- 信号来源。
- 信号采集方式。
- 信号可信度。
- 信号对应的执行节点。
- 信号对应的产物。
- 信号失败时如何处理。

信号可信度建议分级：

- 强信号：机器可验证，例如文件、命令返回码、API 状态。
- 中信号：结构化但可能不完整，例如日志、摘要。
- 弱信号：自然语言说明或人工口头确认。

会触发 `deny` 的状态权限应优先依赖强信号。

### Runtime Engine

Guard Runtime 的核心模块建议：

- `event_loader`：读取和标准化事件。
- `profile_loader`：加载 Guard Profile。
- `activation_handler`：处理显式激活请求，匹配或创建守卫实例。
- `subject_resolver`：计算 subject key。
- `instance_resolver`：根据 Profile 和事件解析明确守卫实例。
- `state_store`：读写当前状态。
- `state_machine`：匹配和执行状态转换。
- `guard_executor`：执行守卫点。
- `artifact_registry`：解析产物定义和产物实例。
- `audit_writer`：写运行审计。
- `brief_renderer`：根据状态生成 Guard Brief。
- `injection_writer`：维护 latest brief 和注入去重记录。
- `handoff_writer`：写交接包。
- `lock_manager`：防止同一 subject 并发写冲突。

这些模块对外暴露一个稳定入口：

```text
guard_runner.py activate --profile <id> --scope current_context
guard_runner.py run --event <event-file>
guard_runner.py brief --profile <id> --subject <subject-key-hash>
```

### 运行结果

运行结果分为：

- allow：允许继续。
- ask：需要用户明确确认。
- deny：当前状态权限拒绝该动作。
- error：运行时错误。
- no_subject_match：主 agent（主代理）事件无法解析守卫实例，不返回 `deny` 但必须审计。
- ambiguous_subject：主 agent（主代理）事件匹配到多个守卫实例，不返回 `deny` 但必须审计。
- no_guard_instance：Hook（钩子）事件无法解析唯一守卫实例，不返回 `deny`，不写审计。
- ambiguous_transition：同一实例内匹配到多个状态转换，属于 Profile 错误。

状态权限 `deny` 结果必须包含：

- 权限结果。
- 命中的权限规则或默认权限。
- 当前工具。
- 当前工具输入摘要。
- 当前状态。
- 失败原因。
- 可用修复建议。
- 审计位置。

守卫点失败结果必须包含：

- 失败守卫点。
- 失败原因。
- 当前状态。
- 需要满足的条件。
- 可用修复建议。
- 是否允许人工覆盖。
- 覆盖记录位置。

### 并发控制

并发控制定义在 `concurrency.yaml`。

要求：

- 同一 subject 写状态时加锁。
- 不同 subject 可以并行。
- 锁路径使用 `subject-key-hash`，完整 Subject Key 只写入状态和审计文件。
- 同一工作树下不同任务不能覆盖彼此状态。
- 同一任务在不同工作树下也要隔离。
- lock 超时后必须写入错误审计。

### 运行时依赖

项目级 Guard Runtime 可以使用 Python 和第三方包。

依赖记录在：

```text
.agents/guard-runtime/requirements.txt
```

初始建议依赖：

- `PyYAML`：读取 YAML 配置。
- `jsonschema`：校验配置和事件。

具体项目如何安装依赖由项目环境规则决定。`agent-guard` 只生成依赖声明，不强行改项目主依赖。

### 逐点迁移

迁移单位是单个守卫点。

流程：

1. 选择一个守卫点。
2. 通过问答式调研确认它守卫什么。
3. 定义输入事件。
4. 定义依赖产物。
5. 定义状态转换。
6. 定义失败行为。
7. 生成配置。
8. 本地验证。
9. 先验证状态推进和产物读取，不配置会拒绝操作的权限规则。
10. 稳定后，在 Guard Profile（守卫画像）的 `states[].permissions` 中为对应状态配置 `ask` 或 `deny` 权限规则。
11. 如有问题，只回滚该守卫点。

不采用全局迁移阶段，避免不同守卫点互相绑定。

## 后续示例：PR review 顺序守卫

`pr-review-order` 可以作为后续项目级流程守卫样例，用于验证具体业务画像生成能力。它不是 MVP 必需内置样例，PR 规则不得写入 Runtime。

### 业务规则

PR 流程要求：

1. 先完成两个独立子 agent 的交叉 review。
2. 两个交叉 review 都完成后，才允许启动安全子 agent 的单独 review。
3. 安全 review 完成后，才允许进入最终提交或推送动作。

### 观察信号

该 Guard Profile 可以观察：

- `UserPromptSubmit`：显式激活或匹配守卫实例。
- `SubagentStart`：观察某类子 agent 是否被启动。
- `SubagentStop`：登记子 agent 输出结果。
- `PreToolUse`：在支持的工具调用前执行权限检查。
- `PostToolUse`：登记工具结果和产物变化。
- `git pre-push`：最终兜底，防止绕过 Codex 过程直接推送。

### 状态示例

```text
cross_review_required
  -> cross_reviews_complete
  -> security_review_required
  -> security_review_complete
  -> ready_to_submit
  -> closed
```

具体状态名、转换和结束条件由 `pr-review-order` Guard Profile 定义。

### 产物示例

- `cross_review_report_a`。
- `cross_review_report_b`。
- `security_review_report`。

这些产物可以是外部引用产物，也可以是守卫自有产物。是否迁移所有权由用户决定。

### 权限和守卫失败示例

如果当前状态仍是 `cross_review_required`，agent 尝试启动安全子 agent：

```text
事件: SubagentStart 或 PreToolUse
动作: start security review
状态权限: deny
结果: deny
状态: 不推进
审计: 写入 run 目录
简报: 生成新的 Guard Brief，提示缺少哪个交叉 review
```

如果 agent 绕过 Codex 过程直接 `git push`：

```text
事件: git pre-push
守卫点:
  - require_two_cross_reviews_complete
  - require_security_review_complete
结果: 缺任一产物则 error/guard_failed
```

### 动态注入示例

首次激活后，Guard Brief 可能显示：

```text
当前状态: cross_review_required
允许下一步:
- 启动 cross_review_agent_a
- 启动 cross_review_agent_b
禁止下一步:
- 启动 security_review_agent
- git push
缺失产物:
- cross_review_report_a
- cross_review_report_b
```

第一个交叉 review 完成后，状态或缺失产物变化，Runtime 生成新的 Guard Brief：

```text
当前状态: cross_review_required
允许下一步:
- 启动 cross_review_agent_b
禁止下一步:
- 启动 security_review_agent
- git push
缺失产物:
- cross_review_report_b
```

两个交叉 review 都完成后，新的 Guard Brief 显示：

```text
当前状态: security_review_required
允许下一步:
- 启动 security_review_agent
禁止下一步:
- git push
缺失产物:
- security_review_report
```

动态注入只来自 Runtime 生成的 latest brief，并通过 `brief_hash` 去重。

## 初始化逻辑

### `my-agent-skills` 初始化

初始化步骤：

1. 新建 GitHub 仓库 `my-agent-skills`。
2. clone 到本地。
3. 创建 `.agents/skills/agent-guard/`。
4. 创建 `AGENTS.md` 和 `CLAUDE.md`。
5. 创建最小文档：
   - `docs/rules/index.md`
   - `docs/adr/index.md`
   - `docs/adr/0001-agent-guard-architecture.md`
6. 创建 `agent-guard` 的 `SKILL.md`。
7. 创建 `references/` 文档。
8. 创建 `assets/templates/` 模板。
9. 创建安装脚本。
10. 做本地最小安装验证。

### 用户级安装

安装脚本职责：

1. 从 `my-agent-skills/.agents/skills/agent-guard` 读取源码。
2. 安装到 `C:\Users\liuli\.agents\skills\agent-guard`。
3. 确认 `SKILL.md` 存在。
4. 确认 `references/`、`assets/`、`scripts/` 存在。
5. 创建或刷新 `C:\Users\liuli\.claude\skills\agent-guard` Junction。
6. 确认 Junction 指向共享 Skill。
7. 输出安装结果。

安装脚本不初始化任何目标项目。

### 项目级初始化

当用户在某个项目内显式要求初始化守卫时，才生成：

```text
.agents/guard-runtime/
.agents/guards/<guard-profile-id>/
```

项目级初始化必须遵守：

- 不修改被守卫对象。
- 不安装 hook，除非用户明确授权。
- 不隐式创建、修改或授权 `deny` 权限规则；`deny` 只由 Guard Profile（守卫画像）的 `states[].permissions` 显式声明。
- 初始状态只生成配置和验证计划。
- Codex hook 可以通过项目级 `.codex/hooks.json` 或受信任的 Guard Plugin 安装。
- Git hook 可以通过项目 `.githooks/` 或仓库约定安装。
- hook 安装只负责接入事件，不写业务规则。

### 用户级守卫初始化

当守卫对象不是某个项目内对象时，可以初始化用户级 Guard Profile：

```text
C:\Users\liuli\.agents\guards\<guard-profile-id>\
```

用户级 Guard Profile 适合：

- 个人通用工作习惯。
- 跨项目通用执行约束。
- 不属于某个 Git 仓库的临时流程。

## 测试决策

初始化阶段只做最小验证，不建立完整测试体系。

好的测试应验证外部行为，不依赖内部实现细节。

第一类验证：安装验证。

- 用户级 Skill 目录存在。
- `SKILL.md` 存在。
- 必要资源目录存在。
- Claude Junction 存在。
- Claude Junction 指向共享 Skill。
- 重复安装不会破坏已有目录。

第二类验证：画像生成验证。

- 能生成项目级 Guard Profile。
- 能生成用户级 Guard Profile。
- `GUARD-MANIFEST.yaml` 存在。
- `target-model.yaml` 存在。
- `activation-model.yaml` 存在。
- `subject-resolver.yaml` 存在。
- `execution-model.yaml` 存在。
- `observation-model.yaml` 存在。
- Guard Brief 模板存在。
- 生成过程不修改被守卫对象。

第三类验证：运行时验证。

- 能加载事件。
- 能加载画像。
- 能从显式激活请求匹配或创建守卫实例。
- 能按 Guard Profile 的 Subject Resolver 解析 subject。
- 主 agent（主代理）事件无法解析实例时写审计但不返回 `deny`。
- 主 agent（主代理）事件多实例歧义时写审计但不返回 `deny`。
- Hook（钩子）事件无法解析唯一实例时忽略，不返回 `deny`，不写审计。
- 能读取当前状态。
- 能匹配状态转换。
- 非推进事件不会进入状态转换匹配，也不写状态推进审计；`state_completed` 无候选转换或没有转换条件满足时返回 error（错误）并写审计。
- 多转换匹配时返回 error。
- 能执行守卫点。
- 守卫通过后推进状态。
- 守卫失败时返回 error 并保持状态。
- 能写入运行审计。
- 状态变化后能生成最新 Guard Brief。
- 注入时能按 `brief_hash` 去重。

第四类验证：并发验证。

- 同一 subject 并发写入时有锁。
- 不同 subject 可以并发运行。
- 多工作树状态互不覆盖。

第五类验证：迁移验证。

- 单个守卫点可以独立启用。
- 单个守卫点可以独立禁用。
- 单个守卫点可以独立回滚。
- 状态权限只影响声明它的状态；守卫点失败只影响当前转换。

第六类验证：最小样例验证。

- 显式激活 `minimal-sample` 后创建或匹配守卫实例。
- 标准事件能按状态机推进状态。
- 主 agent（主代理）事件缺失 Subject（主体）时写审计但不返回 `deny`。
- 主 agent（主代理）事件多实例歧义时写审计但不返回 `deny`；同一实例内多转换歧义时写审计且不推进状态。
- 每次状态或缺失产物变化后，Guard Brief 更新。
- 相同 Guard Brief 不重复注入。

GitHub Actions、目标项目完整测试目录、verify fast/full 暂不进入初始化输出范围。源码仓库可以保留最小自测来防止 Runtime（运行时）和脚本契约漂移。

## 风险与缓解

### 风险：抽象过大，第一版落不下来

缓解：

- 第一版只实现最小 Guard Runtime。
- 第一版只支持有限对象类型，但配置模型预留扩展。
- 第一版按单个守卫点迁移，不追求一次性覆盖全部场景。

### 风险：hook 过早阻断正常工作

缓解：

- hook 安装必须显式授权。
- 会返回 `deny` 的状态权限必须只由 Guard Profile（守卫画像）的 `states[].permissions` 显式声明；审计和回滚依赖 Git。
- 初始画像不默认生成 `deny` 权限规则。

### 风险：守卫画像和被守卫对象漂移

缓解：

- 被守卫对象保持原样。
- Guard Profile 记录对象来源和版本。
- 通过观察信号和产物新鲜度发现漂移。
- 升级由 `agent-guard` 重新调研后执行。

### 风险：用户级和项目级职责混乱

缓解：

- 用户级 `agent-guard` 只生成、安装、升级。
- 项目级 Guard Runtime 负责独立运行。
- 项目级 Guard Profile 负责具体守卫规则。
- 用户级 Guard Profile 只用于非项目对象。

### 风险：运行时和具体流程耦合

缓解：

- Runtime 不写任何具体业务规则。
- Runtime 只认识事件、状态机、守卫点、产物、审计。
- 具体规则写在 Guard Profile。

### 风险：守卫实例匹配错误导致误拒绝

缓解：

- Subject Key 由 Guard Profile 的 Subject Resolver 定义。
- Runtime 不自行猜测实例身份。
- 主 agent（主代理）事件无法解析或解析出多个实例时，不返回 `deny`，但必须写审计。
- Hook（钩子）事件无法解析唯一实例时忽略，不返回 `deny`，不写审计。
- `deny` 结果必须绑定到明确守卫实例。

### 风险：Guard Brief 重复或错误注入导致 agent 混乱

缓解：

- 只有解析到唯一守卫实例才允许注入。
- 注入内容只能来自 Runtime 生成的 latest brief。
- 注入前校验 `subject-key-hash`、`state_version` 和过期时间。
- 按 Codex session 记录已注入 `brief_hash`。
- 相同 `brief_hash` 不重复注入。
- 简报保持固定短格式。

### 风险：Codex hook 无法覆盖所有行为

缓解：

- Codex hook 用于过程观察、动态注入和支持拒绝码入口上的 `deny` 执行。
- Git hook 用于提交或推送前兜底。
- PRD 不承诺通过 Codex hook 拦截所有外部行为。
- 不依赖 Codex 是否读取某个 Skill 文件作为稳定信号。

## 范围外

- 不发布到 GitHub Issue。
- 不创建真实 GitHub 仓库。
- 不落地 `agent-guard` Skill 文件。
- 不修改任何现有项目 Skill。
- 不安装任何 hook。
- 不默认生成 `deny` 权限规则；当前阶段 `deny` 只由 Guard Profile（守卫画像）的 `states[].permissions` 显式声明。
- 不生成具体业务流程的守卫配置。
- 不创建 GitHub Actions。
- 不在目标项目初始化输出中创建完整测试目录。
- 不创建 verify fast/full。

## 术语表

- Agent：执行用户任务的 AI 助手。

- Agent 守卫：对 agent 执行过程进行观察、校验、记录和阻断的旁路机制。

- Skill：给 agent 使用的一组本地说明、脚本、模板和参考资料。

- 被守卫对象：需要被守卫的对象，可以是 Skill、流程、节点、命令、产物生命周期、会话行为或临时任务。

- 守卫画像：某个被守卫对象的完整守卫配置。

- Guard Runtime：项目级或用户级通用守卫运行时，负责执行守卫机制。

- Guard Profile：守卫画像的配置目录。

- 守卫实例：Guard Profile 在某个具体 Subject 上的运行上下文。

- 守卫激活命令：`agent-guard` 提供的显式入口，用于声明当前任务需要某个守卫画像。

- 目标模型：描述被守卫对象是什么。

- Activation Model：描述什么时候可以创建或匹配守卫实例。

- Subject Resolver：Guard Profile 中负责从上下文和事件计算 Subject Key 的规则。

- 执行模型：描述 agent 应该如何推进。

- 观察模型：描述守卫如何判断 agent 做了什么。

- 状态机：描述状态和状态转换的模型。

- 状态转换：从一个状态进入另一个状态的规则。

- 守卫点：某个事件或状态转换上的检查点。

- 守卫类：可复用的守卫类型。

- 产物：执行过程中读取或生成的文件、记录、日志、快照、交接包或外部状态。

- 产物类：可复用的产物定义。

- 产物实例：某一次运行中的具体产物。

- 外部引用产物：由被守卫对象或原流程拥有，守卫只读取和验证。

- 守卫自有产物：由守卫生成和维护。

- 迁移候选产物：当前不属于守卫，但可能更适合由守卫管理的产物。

- Hook：外部触发机制，用于捕获事件并调用守卫运行时。

- Hook 绑定：hook 与守卫事件之间的配置关系。

- Codex 生命周期 hook：Codex 在会话、用户提交、工具调用、子 agent 启停等阶段触发的 hook。

- Git hook：Git 在 commit、push 等操作前后触发的 hook。

- 事件：一次被捕获并标准化的外部输入。

- 标准事件：adapter 输出的统一事件 envelope，供 Guard Profile、状态机和守卫点使用。

- Subject：一次被守卫的具体执行对象。

- Subject Key：Subject 的稳定身份键，用于隔离并发状态。

- subject-key-hash：Subject Key 的 hash，用作运行状态目录路径段。

- Run：一次守卫运行。

- Run ID：一次守卫运行的唯一标识。

- 当前状态：某个 subject 当前所处状态。

- 运行审计：一次守卫运行的详细记录。

- 快照：某一时刻的状态和证据摘要。

- Guard Brief：守卫简报，注入给 agent 的当前守卫状态和下一步要求摘要。

- Guard Injection：守卫注入，把 Guard Brief 提供给 agent 的机制。

- brief_hash：Guard Brief 内容 hash，用于同一 Codex session 内去重。

- 交接包：用于让另一个 agent 接手的上下文包。

- 适配器：把外部系统、hook、命令或文件结果转换成 Guard Runtime 可理解格式的模块。

- `allow`：允许当前工具调用继续。

- `ask`：要求主 agent 取得用户明确确认后重试同一操作。

- `deny`：拒绝当前工具调用继续。

- 人工覆盖：在 Guard Profile 明确允许时，由用户用有过期时间的覆盖记录临时放行某个具体 Subject 和守卫点。

- no_subject_match：事件无法解析到明确守卫实例。

- ambiguous_subject：事件匹配到多个守卫实例。

- ambiguous_transition：同一守卫实例内，一个事件在当前状态下匹配到多个状态转换。

- 运行时独立性：生成后的守卫系统不依赖用户级 `agent-guard` 也能运行。

- Junction：Windows 目录联接，用于让 Claude 的 Skill 目录指向共享 Skill。
