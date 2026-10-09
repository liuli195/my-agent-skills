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
build-and-verify build --project . --pr
build-and-verify verify --project .
build-and-verify verify --project . --execution-context local
build-and-verify verify --project . --execution-context local --diagnostic
build-and-verify verify --project . --base <fixed-commit-or-ref>
build-and-verify verify --project . --pr --base <fixed-commit-or-ref>
build-and-verify verify --project . --full
build-and-verify verify --project . --pr --full
build-and-verify verify --project . --full --performance-report
```

安装后的 `build-and-verify` CLI（命令行程序）直接运行当前项目配置。

## 配置语义

- 目标仓库只定义 `.build-and-verify/config.json` 的 `build.checks` 和 `verify.checks`。
- 每个 check（检查项）必须有非空且同一分组内唯一的 `id`。
- `build.checks[]` 和 `verify.checks[]` 可设置布尔字段 `pr`（拉取请求场景可执行），省略时视为 `true`（可执行）。`pr: false` 仅在显式 `--pr`（拉取请求场景）时排除；本地不带 `--pr` 时仍按原规则运行。
- `--pr` 在 paths（受影响路径）选择和配置变化全选之前过滤检查项，也适用于 `verify --full`（完整验证）。输出中的 `scene`（运行场景）、`checked`（已选检查项）和 `excluded-by-pr`（因拉取请求场景排除的检查项）说明本次范围。
- 拉取请求场景没有选中检查项时报告 `status: skipped`（跳过）；空的拉取请求完整验证不生成 performance report（性能报告）。有效 cache hit（缓存命中）仍视为已检查。
- `verify.checks[].paths` 存在时，默认 verify（快速验证）只选择匹配 changed files（变更文件）的检查项。
- `verify --base <commit-or-ref>`（验证基线）只用于快速验证；系统在验证工作树解析并固定该基线，要求工作树干净，再按固定基线与当前 HEAD（当前提交）的三点差异选择检查项。
- 提供验证基线时不得同时使用 `--full`（完整验证）；无效基线、脏工作树或该组合必须失败，不得退回工作区变更选择。
- `paths` 支持精确文件、目录前缀（如 `docs/`）、尾部递归前缀（如 `src/**`）和 Python fnmatch（通配匹配）模式。
- 没有 `paths` 的 verify check（验证检查项）是 global check（全局检查项）：默认 verify（快速验证）在存在任意 changed file（变更文件）时选择它，干净工作区不选择它。
- 没有 `inputs` 的 global check（全局检查项）使用当前 changed files（变更文件）计算 cache key（缓存键）；需要更稳定缓存时，目标仓库应显式配置 `inputs`。
- 快速验证没有变更时报告 `status: skipped` 和 `reason: no_changed_files`；有变更但没有匹配检查时报告 `status: skipped` 和 `reason: no_matching_checks`。至少选中一个检查时，实际通过或有效缓存命中才报告 `status: passed`，且 `checked`（已检查）必须非空。
- 有 `paths` 但没有 `inputs` 的 verify check（验证检查项）会扫描目标仓库文件来计算 cache key（缓存键）；大型仓库应显式配置 `inputs` 降低默认 verify（快速验证）开销。
- `verify --full`（完整验证）运行当前场景下全部可执行的 `verify.checks`，不读取 cache（缓存）跳过检查；成功通过后会写入或刷新 passed-result cache（通过结果缓存）。
- `verify.fullBudgetSeconds`（完整验证预算秒数）是可选正整数；本机快速与完整验证复用该数值，缺省时不判断总耗时预算。不写死预算值，不改变目标项目已有数值；独立 `build`（构建检查）不纳入。
- `verify.enforceLocalBudget`（本机预算强制开关）必须为布尔值，缺省为 `true`（开启）。明确本机执行的快速及完整验证，每次调用从入口开始共用一个单调时钟截止时间，包含准备、缓存选择、串并行检查。到期停止本次启动的进程及后代，不启动剩余检查，以非零超时失败返回，报告实际耗时、预算、未完成与未启动检查。只回收本次拥有的进程树，不按进程名终止其他程序。
- 设置为 `false`（关闭）时超预算仅输出 `performance-warning`（性能警告）并继续；真实失败、异常、单项超时仍失败。云端、拉取请求和已证明持续集成保留原行为：完整验证只在全部检查结束后判断预算，警告不改变功能验证退出状态。
- 用 `--execution-context local|cloud|ci`（执行地点：本机、云端、持续集成）明确地点，或由宿主会话设置 `BUILD_AND_VERIFY_EXECUTION_CONTEXT`（执行地点环境声明）供入口继承。参数优先于环境声明；显式拉取请求场景、`GITHUB_ACTIONS=true`（代码托管持续集成标识）或 `CI=true`（持续集成声明）优先豁免。`CODEX_CI`（宿主内部标记）、操作系统和模型所在地点不能证明实际执行地点。
- 地点未知时明确警告；配置预算且强制开关开启的正式验证在启动检查前失败，要求声明地点，不静默跳过默认限制。本机技能调用必须明确传入本机地点或继承声明；云端思考、本机执行仍传本机地点。
- `--diagnostic`（本次诊断）临时取消总截止，不改配置默认，保留单项防挂和真实失败；逐检查实时输出开始、结束和耗时，结果为 `status: diagnostic`（诊断完成），不作为正式预算验收通过证据。诊断不读写成功缓存。单个测试用测试框架原生选择及耗时功能调试，插件不新增检查选择器，也不自动解析所有子测试。
- `verify --full --performance-report`（完整验证性能报告）可在无预算或预算内时主动写入同一路径的固定报告。未触发报告时不创建、不覆盖也不删除已有报告。
- performance report（性能报告）保留运行时版本、生成时间、总耗时、预算、超预算状态、验证状态和各检查耗时；本机超预算、硬截止或诊断自动生成 `.build-and-verify/runs/performance-report.json`（性能报告），另加执行地点、诊断标记、原因、未完成与未启动状态。超时、取消、未启动检查不写成功缓存；截止前真实完成的检查可缓存。报告写入失败只输出 `performance-report-warning`（性能报告警告），不改变验证退出状态。
- `verify.timeoutSeconds` 可设置 verify（验证）检查默认 timeout（超时）秒数；`verify.checks[].timeoutSeconds` 可覆盖单个 check（检查项）。未配置时默认 300 秒。强制本机预算下，等待上限取单项超时与剩余总预算的较小值，并区分单项超时和总预算到期。
- 当前仓库的验证配置使用 `pytest-xdist`（Pytest 并行插件）执行 `-n` 并行参数；运行本仓库验证前需要安装 `requirements-dev.txt` 中声明的开发依赖。
- `command` 来自目标仓库配置，按 checked-out repository（已检出仓库）可信输入执行；不要在不信任的仓库内容上运行 build（构建检查）或 verify（验证）。
