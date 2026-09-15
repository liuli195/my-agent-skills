---
name: build-and-verify
description: 本仓库构建检查和验证入口；默认使用 fast（快速）验证
---

# Build and Verify（构建与验证）

Use this skill when this repository needs build（构建检查） or verify（验证） commands.

## 边界

- 作为本仓库 build（构建检查）和 verify（验证）的统一入口。
- 不安装依赖。
- 不写用户级配置。
- 不配置 CI（持续集成）。
- 不内置仓库业务逻辑。
- `init`（初始化）只写入项目配置；`build-and-verify` CLI（命令行程序）是唯一运行入口。
- 默认 verify（验证）使用 fast（快速）模式。
- `--full`（完整）只允许 PR Flow hotfix（拉取请求流程热修复）直推流程和 PR CI（拉取请求持续集成）使用；其它情况禁止使用完整模式，除非用户明确说明原因并确认。

## 命令示例

```bash
build-and-verify init --project .
build-and-verify build --project .
build-and-verify verify --project .
build-and-verify verify --project . --base <fixed-commit-or-ref>
build-and-verify verify --project . --full
build-and-verify verify --project . --full --performance-report
```

安装后的 `build-and-verify` CLI（命令行程序）直接运行当前项目配置。

## 配置语义

- 目标仓库只定义 `.build-and-verify/config.json` 的 `build.checks` 和 `verify.checks`。
- 每个 check（检查项）必须有非空且同一分组内唯一的 `id`。
- `verify.checks[].paths` 存在时，默认 verify（快速验证）只选择匹配 changed files（变更文件）的检查项。
- `verify --base <commit-or-ref>`（验证基线）只用于快速验证；系统在验证工作树解析并固定该基线，要求工作树干净，再按固定基线与当前 HEAD（当前提交）的三点差异选择检查项。
- 提供验证基线时不得同时使用 `--full`（完整验证）；无效基线、脏工作树或该组合必须失败，不得退回工作区变更选择。
- `paths` 支持精确文件、目录前缀（如 `docs/`）、尾部递归前缀（如 `src/**`）和 Python fnmatch（通配匹配）模式。
- 没有 `paths` 的 verify check（验证检查项）是 global check（全局检查项）：默认 verify（快速验证）在存在任意 changed file（变更文件）时选择它，干净工作区不选择它。
- 没有 `inputs` 的 global check（全局检查项）使用当前 changed files（变更文件）计算 cache key（缓存键）；需要更稳定缓存时，目标仓库应显式配置 `inputs`。
- 快速验证没有变更时报告 `status: skipped` 和 `reason: no_changed_files`；有变更但没有匹配检查时报告 `status: skipped` 和 `reason: no_matching_checks`。至少选中一个检查时，实际通过或有效缓存命中才报告 `status: passed`，且 `checked`（已检查）必须非空。
- 有 `paths` 但没有 `inputs` 的 verify check（验证检查项）会扫描目标仓库文件来计算 cache key（缓存键）；大型仓库应显式配置 `inputs` 降低默认 verify（快速验证）开销。
- `verify --full`（完整验证）运行全部 `verify.checks`，不读取 cache（缓存）跳过检查；成功通过后会写入或刷新 passed-result cache（通过结果缓存）。
- `verify.fullBudgetSeconds`（完整验证预算秒数）是可选正整数；缺省时不判断总耗时预算。
- 完整验证只在全部检查结束后判断预算。超预算会输出 `performance-warning`（性能警告）并自动写入 `.build-and-verify/runs/performance-report.json`（性能报告），但不改变功能验证退出状态。
- `verify --full --performance-report`（完整验证性能报告）可在无预算或预算内时主动写入同一路径的固定报告。未触发报告时不创建、不覆盖也不删除已有报告。
- performance report（性能报告）固定记录运行时版本、生成时间、完整验证总耗时、预算、超预算状态、功能验证状态和各检查耗时；报告写入失败只输出 `performance-report-warning`（性能报告警告），不改变功能验证退出状态。
- `verify.timeoutSeconds` 可设置 verify（验证）检查默认 timeout（超时）秒数；`verify.checks[].timeoutSeconds` 可覆盖单个 check（检查项）。未配置时默认 300 秒。
- 当前仓库的验证配置使用 `pytest-xdist`（Pytest 并行插件）执行 `-n` 并行参数；运行本仓库验证前需要安装 `requirements-dev.txt` 中声明的开发依赖。
- `command` 来自目标仓库配置，按 checked-out repository（已检出仓库）可信输入执行；不要在不信任的仓库内容上运行 build（构建检查）或 verify（验证）。
