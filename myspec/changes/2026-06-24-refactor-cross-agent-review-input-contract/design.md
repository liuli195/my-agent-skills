## Context

`cross-agent-review`（跨代理审查）用于生成独立审查证据。`Comet`（双星流程）、`PR Flow`（拉取请求流程）和用户手动调用只是不同调用方；插件本身不应理解这些流程的内部产物。

现有脚本把 `diff.patch`（差异补丁）作为核心输入之一，并在 Python 代码中硬编码 `reviewer prompt`（审查提示词）。这让契约容易退回“大文件输入”模式，也让提示词维护和脚本行为混在一起。

脚本内部已经有两层超时：单个 `reviewer`（审查代理）480 秒、整体 `SDK dispatch`（开发包派发）540 秒。主 `agent`（代理）如果在外层再包更短的计时器，会提前终止插件，导致插件无法产出结构化超时结果。

## Goals / Non-Goals

**Goals:**

- 把审查对象契约写成明确规则：`base_ref`（基线引用）和 `head_ref`（头引用）定义 review subject（审查对象）。
- 让 `review agent`（审查代理）根据 `manifest`（清单）里的 git commands（命令）、commit list（提交列表）和 changed files（变更文件）按需读取。
- 将 `reviewer prompt`（审查提示词）正文结构抽到独立模板文件，方便修改和复用；Python 脚本仍是调用方和渲染入口。
- 明确主 `agent`（代理）不得用外层短 `timeout`（超时）包装插件调用。
- 用测试锁住提示词不内联大输入和超时说明。

**Non-Goals:**

- 不改变四个 reviewer role（审查角色）。
- 不改变 severity（严重级别）和 `review-pass.json`（通过标记）契约。
- 不让 `cross-agent-review`（跨代理审查）运行构建或测试。
- 不把插件核心契约耦合到任何调用方流程或流程产物。
- 不安装或改动用户环境里的插件。

## Decisions

1. 用 review subject（审查对象）替代 diff file（差异文件）作为核心边界。

   CLI（命令行接口）保留 `--base-ref` 和 `--head-ref`，移除核心必需的 `--diff-file`。脚本从 git（版本控制）生成三点 diff（三点差异）命令、commit list（提交列表）和 changed files（变更文件）。这让审查范围可复现，也避免把大 diff output（差异输出）变成 reviewer（审查者）的默认上下文。

2. 将 `manifest`（清单）升级为审查范围入口。

   `manifest`（清单）记录 `git diff <base_ref>...<head_ref>`、`git log <base_ref>..<head_ref> --oneline`、`git diff --name-status <base_ref>...<head_ref>`、`git diff <base_ref>...<head_ref> -- <path>` 模板、merge base（合并基点）、commit list（提交列表）、changed files（变更文件）和上下文文件元数据。

3. 将 `reviewer prompt`（审查提示词）限定为索引和读取策略。

   `prompt`（提示词）应包含 role（角色）、输出格式、severity rubric（严重级别规则）、review subject（审查对象）、manifest path（清单路径）、commands（命令）、changed files（变更文件）和上下文文件元数据。它不应包含完整正文，尤其不能包含大 `diff`（差异）。

4. 抽出提示词模板。

   新增插件内模板文件，例如 `assets/templates/reviewer-prompt.md`。脚本提供小型模板渲染函数，使用明确的占位符替换，不引入新依赖。这样提示词文字可以独立修改和复用，脚本只保留数据收集、模板渲染和派发逻辑。

5. 把超时归属放在插件内部。

   插件脚本内部能把超时转换成结构化 CRITICAL finding（严重发现项）并写入常规输出。外层短 `timeout`（超时）会绕过这条路径，因此调用说明必须明确禁止。

6. 测试覆盖契约而不是只覆盖当前字符串。

   测试应检查大输入不出现在 `prompt`（提示词）中、`prompt`（提示词）长度保持受控、超时常量仍为 480/540 秒，以及技能说明不建议外层短超时。

## Risks / Trade-offs

- [Risk] reviewer agent（审查代理）可能少读必要上下文 → Mitigation: `prompt`（提示词）保留 `manifest`（清单）、上下文路径、哈希和按需读取指令，并允许只读 `git diff/show/status`（差异/显示/状态）命令补足。
- [Risk] 过度限制 `prompt`（提示词）导致审查质量下降 → Mitigation: 只限制初始上下文体积，不限制 reviewer agent（审查代理）按需读取源文件和路径范围差异。
- [Risk] 调用方仍用外层工具加短超时 → Mitigation: 在 `SKILL.md`（技能说明）和规格中写成禁止项，并增加文本回归检查。
- [Risk] 简单模板渲染能力不足 → Mitigation: 模板只承担静态提示词和已预渲染变量插入，不在模板里做复杂逻辑。
