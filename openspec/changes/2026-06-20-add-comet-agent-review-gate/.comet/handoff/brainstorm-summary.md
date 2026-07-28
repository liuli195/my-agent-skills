# Brainstorm Summary

- Change: add-comet-agent-review-gate
- Date: 2026-06-20

## 已确认事实

- 目标是在 Comet build 完成后、verify 前增加 agent review gate（代理审查门禁）。
- 不新增 Comet phase（阶段），不修改 `.comet.yaml` 主状态机字段，不新增 reviewed wrapper（审查包装入口）。
- 门禁必须使用 Agent Guard Global Command Guard（全局命令守卫点），并配置为用户级 Guard Profile（守卫画像）。
- 用户级静态规则位于 `~/.agents/guards/<profile_id>/global-command-guards.yaml`；项目命令的 audit（审计）和运行态材料仍按项目运行态处理。
- 主拦截点是 `comet-guard.sh <change> build --apply`，因为它发生在 phase 从 build 进入 verify 前。
- `comet-guard.sh <change> verify --apply` 是 verify 完成后的状态推进，不是主要拦截点。
- 命令模式必须覆盖直接脚本调用、路径脚本调用和 `"$COMET_BASH" "$COMET_GUARD" <change> build --apply` 这类环境变量调用。
- 必须复用 Agent Guard 的 `artifacts.yaml` 产物注册层。Global Command Guard 通过 `artifact` / `artifact_id` 引用注册产物，而不是维护一套独立 evidence path（证据路径）模型。
- cross-agent-review（跨代理审查）的边界行为不得修改：默认输出仍是 `.local/cross-agent-review/<change>/<head_ref>/`，只有通过时才生成 `review-pass.json`。
- `cross_agent_review_pass` artifact path 指向 `.local/cross-agent-review/{change}/{git_head}/review-pass.json`，按当前项目根目录解析。
- Global Command Guard 校验 `review-pass.json` 的 `status`、`change`、`head_ref`、`blocking_findings`、`report`、`report_hash`。
- deny（拒绝）后 agent 必须先跑非变更 build readiness check（构建就绪检查），例如 `comet-guard.sh <change> build`；通过后再准备 cross-agent-review 输入。
- cross-agent-review 输入必须包含 `--change`、`--base-ref`、`--head-ref`、`--diff-file`、`--spec-file`、`--design-file`、`--tasks-file` 和 `--tests-file`；`--head-ref` 必须等于当前 HEAD，worktree 必须干净，测试结果必须已由调用方保存。
- 前置归档变更遗漏了 Agent Guard 各 Skill 入口和共享参考文档对 Global Command Guard 的说明；当前 change 必须补齐。
- Agent Guard Skill 入口和共享参考文档的更新必须符合四条标准：渐进式披露、按 agent 使用场景组织、明确禁止项、语言简洁高效。

## 已否决方案

- 新增 `/comet-reviewed` 或类似 wrapper：已否决。Global Command Guard 已经负责拦截受保护命令，wrapper 会重复编排并改变插件边界。
- 使用 Gate Binding（门禁绑定）表达该边界：已否决。当前方案使用 Global Command Guard。
- 要求 cross-agent-review 改默认输出目录、传 `--output-dir` 到 `.local/guard/evidence`、或复制 pass marker：已否决。产物注册层就是为解耦这类路径问题而存在。
- 以 `comet-guard.sh <change> verify --apply` 作为主拦截点：已否决。该命令太晚，已经属于 verify 完成边界。

## 确认的技术方案

- 新增或更新用户级 Guard Profile sample/template，声明 `global-command-guards.yaml` 和配套 `artifacts.yaml`。
- `global-command-guards.yaml` 匹配 build 阶段收尾命令：`comet-guard.sh <change> build --apply`，并提取 `change`。
- `artifacts.yaml` 注册 `cross_agent_review_pass`，路径为 `.local/cross-agent-review/{change}/{git_head}/review-pass.json`。
- Runtime 需要让 Global Command Guard evidence evaluation（证据评估）支持 `artifact` / `artifact_id`，从同一 Guard Profile 的 `artifacts.yaml` 查找并渲染 path。
- 对项目命令，即使 profile 来自用户级，artifact 相对路径也按项目根目录解析；不能解析到用户 profile 目录或 `~/.agents/guard`。
- artifact path 支持命令捕获和 `{git_head}` 等全局守卫上下文，不强制依赖 Session Focus 的 `{instance_id}` / `{state_version}`。
- evidence 缺失、过期或 JSON predicate 不通过时，Global Command Guard 返回 deny，输出 reason、next、suggestion、captures、failing guards 和 artifact 信息。
- agent 收到 deny 后按顺序执行：build readiness check -> 准备 review 输入 -> 运行 cross-agent-review -> 重新执行 build `--apply`。
- cross-agent-review 仍保持独立：不运行构建或测试，不推进 Comet phase，只生成 review report 和 pass marker。
- Comet verify 仍由原流程负责，只有 build `--apply` 通过用户级 Global Command Guard 后才进入 `/comet-verify`。
- 更新 `$agent-guard`、`$agent-guard-install`、`$agent-guard-init`、`$agent-guard-update`、`$agent-guard-run` 和共享模板索引，使 Global Command Guard 可被发现、安装、同步、运行反馈和排障。
- 这些文档必须按 install/init/update/run/troubleshoot 等 agent 使用场景组织；入口只放立即可执行步骤和下一跳链接，细节放 reference/template；禁止项必须直接列明；语言保持短句和可执行表达。

## 风险

- 当前 Global Command Guard runtime 仍偏向 legacy `evidence.path` 模型，需要接入 `artifacts.yaml`；若不能纯配置解决，必须先把原因和修改点提交用户评审。
- 命令匹配过窄会漏拦真实 Comet 调用；profile sample 必须覆盖直接、路径和环境变量调用形态。
- deny 后直接 review 会绕过 build 收尾失败；必须先做 build readiness check。
- `git_head` 和 cross-agent-review `--head-ref` 不一致会造成 stale pass marker；两者必须绑定当前 HEAD。
- Agent Guard skill 入口文档若不更新，会导致能力只存在于 runtime README，用户无法从正常入口维护全局守卫。

## 测试策略

- Validator tests（校验器测试）覆盖 Global Command Guard 引用 `artifacts.yaml` 中已注册 artifact，拒绝未知 artifact。
- Runtime tests（运行时测试）覆盖 artifact path 渲染 `{change}` 和 `{git_head}`，并读取 `.local/cross-agent-review/<change>/<head_ref>/review-pass.json`。
- Runtime tests 覆盖 missing pass marker、stale `head_ref`、blocking findings 和 valid pass marker allow。
- Integration tests（集成测试）覆盖直接、路径、`$COMET_GUARD` 三类命令模式都能拦截 build `--apply`。
- Flow tests（流程测试）覆盖 deny 后先 build readiness check，再 cross-agent-review，再 retry build `--apply`。
- Package/docs tests（包和文档测试）覆盖 Agent Guard skill entrypoints 和 template index 暴露 Global Command Guard 说明。
- 回归确认 cross-agent-review 不推进 Comet phase，Comet verify 仍由原流程负责。

## Spec Patch

- 已回写当前 change 的 `proposal.md`、`design.md`、`tasks.md` 和 delta spec，使方案统一为 Global Command Guard + artifacts.yaml + cross-agent-review pass marker。
