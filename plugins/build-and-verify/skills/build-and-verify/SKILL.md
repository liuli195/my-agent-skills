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

- 目标仓库使用 `.build-and-verify/config.json`，继续由 `build.checks` 和 `verify.checks` 定义检查。
- `version: 1`（旧配置）不自动改写、不自动限制，验证明确输出 `legacy-unprotected`（旧模式未保护）；旧命令及工具链保持原行为，不能把旧成功当作新保护证据。
- 新初始化默认 `version: 2`（新配置），必须显式声明 `verify.realChecks`（真实检查标识清单）。纯内存项目使用空清单 `[]`；有真实场景时可登记一项或多项，标识必须对应现有验证检查且不能重复。清单只声明角色，不自动选中检查，也不改变路径、差异、拉取请求及完整验证的选择语义。
- 未登记的检查默认以运行时守卫执行；当前 Python（编程语言）适配支持直接脚本、模块、pytest（测试框架）与其 unittest（标准测试框架）收集，保留字符串／列表、成功续行、环境赋值、引号和测试参数。未知工具链或尚未完成保护的语言段明确输出 `runtime_guard_uncovered_command`（保护未覆盖命令）并失败，不无保护执行或自动改登记为真实检查。
- 显式迁移复用 `init --config <已确认配置> --overwrite`（初始化覆盖命令），写入前校验并备份旧配置；同秒备份增加序号，不覆盖旧备份。明确回退时使用同一覆盖命令指定备份文件，恢复旧配置后仍标明未保护。不得失败后静默恢复旧模式报成功。
- Python（编程语言）守卫先于项目代码、导入和准备加载，也覆盖清理、辅助函数、线程及重新创建的 pytest-xdist（并行测试插件）工作进程。业务子进程、网络及真实文件变更被拒，必要读取和内存计算保留；捕获违规异常仍失败，保护证据缺失、工作进程崩溃或退出不完整也失败。
- 框架仅使用固定受限的本地工作进程启动与捕获记账通道，不整体放开控制端、调用栈或临时目录；保留原有外层并行、工作进程数和插件加载参数，不统一关闭即时编译。框架缓存记账在进程内完成，不把文件写权限交给普通测试。
- 成功缓存区分新旧策略、适配器、普通／真实角色和真实清单；真实角色成功不能供普通保护角色复用。守卫不是恶意代码或原生程序安全沙箱，已知原生库内部文件行为仍需对应适配及真实验收，不能仅凭 Python（编程语言）审计事件宣称已全面覆盖。
- DuckDB（分析数据库）本期不提供普通无副作用保证，相关场景包含纯内存场景须显式登记为聚焦的真实检查，仍真实运行及保留并行，报告不可计为已保护。普通模式遇到该库明确未覆盖并失败，不自动登记、不放开整个测试组。其它新发现的原生缺口同样先报告，不自动放行。
- SQLite（标准数据库）保留 `:memory:`（内存库）与明确 `uri=True`（启用数据库网址）、唯一 `mode=ro`（只读模式）的文件读取，不自动改写任意网址。普通模式临时存储固定内存，`PRAGMA temp_store`（临时存储查询）返回2；业务授权回调可设置、替换及清除自己的部分，守卫回调不可被清除。文件附加、另存数据库、改回磁盘临时存储和只读库写企图独立记账，吞数据库异常仍失败。

## 新模式当前未覆盖的入口

- 非 Python（编程语言）段及混合命令中的未实现语言段，在对应适配完成前明确失败；不能用真实角色整组放开未知测试。
- 普通检查中的包管理／环境封装命令、非 `&&`（成功续行）的 shell（命令解释器）语法、未适配的 Python（编程语言）启动选项与独立 pytest（测试框架）可执行文件，均明确未覆盖，不猜测安全；旧配置仍原样执行。
- pytest-xdist（并行测试插件）仅适配默认本地工作进程，远程、自定义解释器、工作目录及环境的启动规格未覆盖，不回退无保护执行。
- SQLite（标准数据库）支持公开连接类派生的类形式 factory（连接工厂）；任意可调用工厂、绕过公开连接类的私有原生连接及其它未覆盖的网址形式明确失败，不默默转换工厂或任意放行。已查消费范围未发现任意可调用工厂，不代表所有项目均兼容。
- DuckDB（分析数据库）遵循上述显式真实检查边界；其他原生库新发现的正常漏拦需单独报告，不能据本守卫宣称全原生覆盖。命令行及性能报告均区分 `ordinary-guarded`（普通守卫角色）与 `real-unprotected`（真实未保护角色）。
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
