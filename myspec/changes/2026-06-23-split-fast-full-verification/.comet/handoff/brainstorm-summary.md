# Brainstorm Summary

- Change: split-fast-full-verification
- Date: 2026-06-23

## 确认的技术方案

构建一个轻量 `test-framework` Plugin（测试框架插件），同时提供 Claude（Claude 版本）和 Codex（Codex 版本）包装。插件只保留三项核心能力：初始化标准产物结构、提供快速缓存验证、提供统一配置和统一命令入口。

目标仓库只维护 `.test-framework/config.json`，并且只定义一套 `build.checks` 和 `verify.checks`。默认 `python <test-framework-script> verify --project <repo>` 在 `verify.checks` 上应用 changed-files（变更文件）筛选和 passed-result cache（通过结果缓存）；`python <test-framework-script> verify --project <repo> --full` 运行完整 `verify.checks`。目标仓库不定义独立 fast（快速验证）测试清单。配置使用 JSON（数据格式），避免任意目标仓库额外依赖 YAML（配置格式）解析库。

默认 changed-files（变更文件）来源是 worktree（工作区），包含 staged tracked changes（已暂存已跟踪变更）、unstaged tracked changes（未暂存已跟踪变更）和 untracked non-ignored files（未跟踪且未忽略文件）。首版不提供其他命令参数。

## 关键取舍与风险

- 插件不内置 PR Flow（拉取请求流程）、Release Flow（发布流程）、Comet（双星流程）或本仓库业务逻辑，业务映射只存在于目标仓库配置。
- fast（快速验证）是框架执行模式，不是仓库配置能力。
- cache（缓存）只复用已选中 checks（检查项）的 passed（已通过）结果；cache miss（缓存未命中）运行该 check（检查项）本身；failed（失败）不缓存。
- A 不改造 PR Flow（拉取请求流程）hotfix（热修复）或其他接入方；这些接线后续可独立处理。
- full（全量验证）耗时优化拆到 `optimize-full-verification-runtime` 变更。

## 测试策略

- 覆盖插件双 manifest（清单）和 marketplace（市场目录）/projection（发布投影）登记。
- 覆盖初始化产物：`.test-framework/config.json`、`.test-framework/.gitignore` 和 `.test-framework/cache/`，并确认不复制 runner（运行器）到目标仓库。
- 覆盖统一入口：`build`、默认 `verify`、`verify --full`。
- 覆盖 changed-files（变更文件）选择、cache hit（缓存命中）、cache miss（缓存未命中）、failed（失败）不缓存、no-check（无检查）不回退 full（全量验证）。
- 覆盖临时目标仓库端到端初始化后可运行 `build`、`verify`、`verify --full`。

## Spec Patch

已回写 delta specs（增量规格）：新增 `test-framework-plugin` 能力，更新 `local-verification-modes` 为同一套 configured checks（配置检查项）上的默认 fast（快速验证）和显式 full（全量验证），更新 `local-plugin-build-checks` 语义；PR Flow（拉取请求流程）已从 A 范围剔除。
