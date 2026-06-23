## Context

变更前旧入口 `python scripts/check.py verify` 默认运行完整 pytest（Python 测试框架）套件。本机实测 341 个测试约 214 秒，其中 `test_pr_flow_cli.py` 单文件约 135 秒。用户确认 A 的目标不是做本仓库专用 fast（快速验证），而是升级为可复用的 test-framework Plugin（测试框架插件）：定义标准产物结构、提供快速缓存验证能力、提供统一配置和统一命令入口。

## Goals / Non-Goals

**Goals:**
- 提供同时支持 Claude（Claude 版本）和 Codex（Codex 版本）的轻量 `test-framework` Plugin（插件）。
- 初始化目标仓库的最小标准结构：`.test-framework/config.json`、`.test-framework/.gitignore` 和 `.test-framework/cache/`。
- 目标仓库只定义一套 canonical checks（标准检查项）；默认 `verify` 在这套检查上应用 changed-files（变更文件）筛选和 passed-result cache（通过结果缓存），`verify --full` 运行完整检查集且通过项刷新 passed-result cache（通过结果缓存）。
- 保留一个统一配置文件和一个统一命令入口。

**Non-Goals:**
- 不内置 PR Flow（拉取请求流程）、Release Flow（发布流程）、Comet（双星流程）或本仓库业务检查逻辑。
- 不生成业务测试、不维护固定烟雾测试清单、不让目标仓库单独定义 fast（快速验证）。
- 不管理 CI（持续集成）、不安装插件到用户环境、不写用户级配置。
- 不改造 PR Flow（拉取请求流程）等接入方；它们后续可独立接入 `verify --full`。
- 不在本 change（变更）中优化慢测试或新增并行测试依赖。

## Decisions

1. 插件保持薄包装。
   - 产物为 `plugins/test-framework/.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 和一个 `skills/test-framework` Skill（技能）。
   - 不拆多个 Skill（技能）入口；脚本提供 `init`（初始化）、`build`（构建检查）和 `verify`（验证）模式。
   - 发布投影和 marketplace（市场目录）同时登记 Claude（Claude 版本）与 Codex（Codex 版本）。

2. 目标仓库初始化最小结构。
   - 插件自带 `scripts/test_framework.py` 是唯一 runner（运行器）入口，目标仓库不复制 runner（运行器）。
   - `.test-framework/config.json` 是唯一配置，使用 Python（运行器）标准库解析，避免目标仓库额外依赖。
   - `.test-framework/.gitignore` 只覆盖框架本地运行态。
   - `.test-framework/cache/` 是本地缓存目录，不作为提交产物。
   - 初始化遇到已有 `.test-framework/config.json` 或 `.test-framework/.gitignore` 时必须拒绝覆盖并报告冲突，除非未来显式增加覆盖参数。
   - 项目级安装时命令可指向仓库内插件路径；用户级安装时由 agent（代理）使用当前 Skill（技能）路径调用同一个 `scripts/test_framework.py`。

3. fast（快速验证）是框架执行模式，不是目标仓库配置能力。
   - 目标仓库只声明 `build.checks` 和 `verify.checks`。
   - `python <test-framework-script> verify --project <repo> --full` 运行全部 `verify.checks`，不得读取 cache（缓存）来跳过 check（检查项）。
   - `python <test-framework-script> verify --project <repo>` 默认从 worktree（工作区）收集 changed files（变更文件），包含 staged tracked changes（已暂存已跟踪变更）、unstaged tracked changes（未暂存已跟踪变更）和 untracked non-ignored files（未跟踪且未忽略文件）。
   - 框架选择受影响的 `verify.checks`，并对这些检查应用 passed-result cache（通过结果缓存）。
   - 没有 `paths` 的 check（检查项）是 global check（全局检查项）：默认 `verify` 在存在任意 changed file（变更文件）时选择它，干净工作区不选择它。
   - cache miss（缓存未命中）时只运行该检查本身；default verify（默认验证）和 `verify --full` 都只在 check（检查项）通过后写入或刷新 passed-result cache（通过结果缓存）；failed（失败）结果不写入缓存；没有受影响检查时输出 checked（已检查）为空和 full-not-run（全量未运行）提示。
   - 没有 `inputs` 的 global check（全局检查项）使用当前 changed files（变更文件）作为 cache input（缓存输入）；需要稳定缓存命中的目标仓库应显式配置 `inputs`。
   - 有 `paths` 但没有 `inputs` 的 check（检查项）会扫描目标仓库文件来计算 cache key（缓存键）；大型仓库应显式配置 `inputs` 降低默认 `verify` 开销。
   - `command` 来自目标仓库配置，按 checked-out repository（已检出仓库）可信输入执行；不要在不信任的仓库内容上运行 build（构建检查）或 verify（验证）。
   - 首版不提供 timeout（超时）配置；可能长时间运行的 `command` 应由目标仓库脚本自行实现超时控制。

4. 统一命令面保持小。
   - 必须支持 `python <test-framework-script> build --project <repo>`、`python <test-framework-script> verify --project <repo>`、`python <test-framework-script> verify --project <repo> --full`。
   - 首版不提供其他命令参数，避免扩大能力边界。

## Risks / Trade-offs

- [Risk] 配置过度抽象会变重。Mitigation: 首版只支持 `id`、`paths`、`command`、`inputs` 这组检查字段。
- [Risk] fast（快速验证）规划不完整会漏掉检查。Mitigation: 契约测试覆盖路径匹配、cache hit（缓存命中）、cache miss（缓存未命中）、failed（失败）不缓存和 no-check（无检查）输出。
- [Risk] 双版本插件结构漂移。Mitigation: build（构建检查）继续验证 Claude（Claude 版本）和 Codex（Codex 版本）manifest（清单）与 marketplace（市场目录）一致。
