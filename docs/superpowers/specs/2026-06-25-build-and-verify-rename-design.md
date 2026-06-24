---
comet_change: rename-test-framework-to-build-and-verify
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-24-rename-test-framework-to-build-and-verify
status: final
---

# Build and Verify Rename Design

## 目标

将现有 `test-framework`（测试框架）Plugin（插件）按同一能力 rename（改名）为 `build-and-verify`（构建与验证）。本次只做 rename（改名）和必要引用同步，不重构、不重写 runner（运行器）逻辑。

## 范围

本次 rename（改名）覆盖：

- 插件目录：`plugins/test-framework` -> `plugins/build-and-verify`
- Skill（技能）目录：`skills/test-framework` -> `skills/build-and-verify`
- 脚本入口：`test_framework.py` -> `build_and_verify.py`
- runner（运行器）：`test_framework_runner.py` -> `build_and_verify_runner.py`
- 配置目录：`.test-framework` -> `.build-and-verify`
- 活跃命令引用：Comet（双星流程）、PR Flow（拉取请求流程）、marketplace（市场目录）、release projection（发布投影）、OpenSpec（开放规格）和测试引用

根目录 `pyproject.toml`（Python 测试配置）在本次范围内删除。pytest（Python 测试运行器）需要的路径和参数必须在 `.build-and-verify/config.json` 的命令中显式声明。

发布说明：本仓库不再把裸 `pytest`（Python 测试运行器）或 `pip install -e .`（可编辑安装）作为 Plugin（插件）/Skill（技能）开发入口；开发与验证入口统一为 `build-and-verify`（构建与验证）。

## 非目标

- 不重构或重写现有 test-framework（测试框架）实现。
- 不改变 build（构建检查）或 verify（验证）执行逻辑。
- 不改变 configured checks（配置检查项）的覆盖范围。
- 不新增 PR CI（拉取请求持续集成）工作流。
- 不让 cross-agent-review（跨代理审查）运行 build（构建检查）或测试。
- 不新增用户级安装或修改用户级配置。

## 设计决策

### 1. 使用机械 rename（改名）

实现应优先使用移动文件和字符串替换。`init`（初始化）、`build`（构建检查）、`verify`（验证）、cache（缓存）、changed files（变更文件）选择和 parallel execution（并行执行）逻辑保持原样。

这避免把 #70 变成 runner（运行器）重写或验证框架重构。

### 2. 不保留旧入口

旧 `test-framework`（测试框架）入口不保留兼容 wrapper（包装入口）。活跃自动化、配置和测试应统一指向 `build-and-verify`（构建与验证）。

需要主动检查并移除以下活跃引用：

- `plugins/test-framework`
- `skills/test-framework`
- `.test-framework`
- `test_framework.py`
- `test_framework_runner.py`

历史 archive（归档）文档可以保留旧名称，不作为活跃入口。

### 3. 保留验证模式边界

`verify`（验证）默认 fast（快速）。`--full`（完整）只允许：

- PR Flow（拉取请求流程）hotfix（热修复）直推验证命令。
- PR CI（拉取请求持续集成）。

其他上下文如果要运行 `--full`（完整），agent（代理）必须说明升级原因并等待用户确认。

Comet（双星流程）的默认 `verify_command`（验证命令）必须使用 fast（快速）入口，不得包含 `--full`。

### 4. 删除根目录 Python 测试配置

删除根目录 `pyproject.toml`（Python 测试配置）后，pytest（Python 测试运行器）的测试路径和参数不能依赖隐式配置。`.build-and-verify/config.json` 中每条 pytest（Python 测试运行器）命令必须显式包含所需测试文件或目录，以及需要的命令参数。

## 风险与缓解

- 漏改活跃引用：用 `rg`（快速搜索）检查活跃配置和测试，不把 archive（归档）历史当作失败。
- pytest（Python 测试运行器）默认行为变化：把必要参数写进 `.build-and-verify/config.json` 命令，并用 focused tests（聚焦测试）验证。
- 旧入口残留：增加或更新测试，确保活跃自动化不引用旧入口。
- 范围扩大：任务中明确禁止 refactor（重构）和 rewrite（重写）runner（运行器）。

## 测试策略

- 运行 build-and-verify（构建与验证）插件行为测试，证明 rename（改名）后 init/build/verify（初始化/构建检查/验证）逻辑不变。
- 运行 local build contract（本地构建契约）测试，确认活跃命令只指向新入口。
- 运行 PR Flow（拉取请求流程）测试，确认 hotfix（热修复）使用显式 `--full`，complete/tweak（收尾/小改）不隐式升级。
- 运行 OpenSpec（开放规格）严格校验。
- 最后运行 `build-and-verify`（构建与验证）的默认 fast verify（快速验证）；本非 hotfix（非热修复）、非 PR CI（非拉取请求持续集成）流程不运行 full verify（完整验证）。
