## Context

`test-framework`（测试框架）Plugin（插件）最初用于拆分默认 fast verify（快速验证）和显式 full verify（完整验证），但当前仓库已经把它作为统一 build（构建检查）和 verify（验证）入口使用。名称继续停留在 test framework（测试框架）会误导后续流程：需要构建或验证时，agent（代理）可能绕开该 Skill（技能），或把 full verify（完整验证）当成默认验证。

当前根目录 `pyproject.toml`（Python 测试配置）只保存 pytest（Python 测试运行器）发现范围和 `-q`（安静输出）参数。删除它后，测试行为必须由 `build-and-verify`（构建与验证）配置中的显式命令表达，避免根目录保留第二个测试行为入口。

本变更按 rename（改名）处理同一个 Plugin（插件）能力，不按删除旧能力再新增新能力处理。

## Goals / Non-Goals

**Goals:**

- 将插件、Skill（技能）、脚本、配置目录和文档统一改名为 `build-and-verify`（构建与验证）。
- 不保留旧 `test-framework`（测试框架）兼容入口，避免多个入口长期并存。
- 删除根目录 `pyproject.toml`（Python 测试配置），把 pytest（Python 测试运行器）参数显式写入 `.build-and-verify/config.json` 的命令。
- 保留已有 fast verify（快速验证）和 full verify（完整验证）执行语义。
- 明确 full verify（完整验证）只允许 PR Flow（拉取请求流程）hotfix（热修复）直推和 PR CI（拉取请求持续集成）使用；其他自动流程默认使用 fast verify（快速验证）。

**Non-Goals:**

- 不让 cross-agent-review（跨代理审查）运行构建或测试。
- 不重构或重写现有 test-framework（测试框架）实现；本次只做 rename（改名）和必要引用同步。
- 不新增用户级安装或修改用户级配置。
- 不新增 PR CI（拉取请求持续集成）工作流；本次只定义 PR CI（拉取请求持续集成）允许使用 full verify（完整验证）的边界。
- 不改变 configured checks（配置检查项）的业务覆盖范围。

## Decisions

1. **采用 `build-and-verify`（构建与验证）作为唯一公共名称。**

   备选 `repo-checks`（仓库检查）更短，但不能直接表达两个命令族；`repo-verification`（仓库验证）漏掉 build（构建检查）。`build-and-verify`（构建与验证）直接对应插件职责和用户请求。

2. **按同一能力 rename（改名），不保留兼容 wrapper（包装入口）。**

   旧目录 `plugins/test-framework/`、Skill（技能）名 `test-framework`、脚本 `test_framework.py` 和配置目录 `.test-framework/` 全部替换为 `build-and-verify`（构建与验证）命名。OpenSpec（开放规格）delta 在 `test-framework-plugin`（测试框架插件）能力下表达 rename（改名）和行为修改，不新增独立 `build-and-verify-plugin`（构建与验证插件）能力，也不把旧能力标记为 removed（移除）。

3. **删除根目录 Python（Python 语言）测试配置。**

   `pyproject.toml`（Python 测试配置）中的 `testpaths`、`python_files` 和 `addopts` 不再作为隐式行为来源。每个 pytest（Python 测试运行器）命令必须显式写出测试路径和所需参数，例如 `-q`（安静输出）。

4. **full verify（完整验证）边界由文档和测试共同约束。**

   `build-and-verify verify --project .` 默认仍是 fast verify（快速验证）；`--full`（完整模式）保留给显式命令。仓库内只有 `.pr-flow/config.yaml` 的 hotfix（热修复）验证命令和未来 PR CI（拉取请求持续集成）配置可以引用 `--full`（完整模式）。Comet（双星流程）默认 verify（验证）命令不得引用 `--full`。

5. **PR CI（拉取请求持续集成）只定义允许边界，不在本变更创建。**

   当前仓库只有 release（发布）工作流，没有 PR CI（拉取请求持续集成）。为避免超出 #70，本次不新增 workflow（工作流）文件，只在规格和测试中允许未来 PR CI（拉取请求持续集成）引用 full verify（完整验证）。

## Risks / Trade-offs

- **旧安装路径失效** -> 这是刻意的 breaking change（破坏性变更）；通过 release（发布）说明和测试禁止旧入口残留来降低误用。
- **删除 `pyproject.toml`（Python 测试配置）后 pytest（Python 测试运行器）默认行为变化** -> 所有仓库验证命令必须显式传入测试路径和 `-q`（安静输出）等参数。
- **大量字符串引用需要同步** -> 用 package（包）测试、local build contract（本地构建契约）测试和 OpenSpec（开放规格）校验覆盖 marketplace（市场目录）、projection（发布投影）、Comet（双星流程）和 PR Flow（拉取请求流程）引用。
- **历史设计文档仍包含旧名称** -> archive（归档）历史不重写；活跃规格和运行入口必须更新。

## Migration Plan

1. 移动插件目录和 Skill（技能）目录到 `build-and-verify`（构建与验证）命名。
2. 重命名脚本和 runner（运行器）文件，并更新内部 `argparse`（命令行解析）名称。
3. 移动 `.test-framework/` 到 `.build-and-verify/`，更新缓存目录排除和配置读取路径。
4. 删除 `pyproject.toml`（Python 测试配置），把 pytest（Python 测试运行器）参数写入 `.build-and-verify/config.json`。
5. 更新 Comet（双星流程）、PR Flow（拉取请求流程）、marketplace（市场目录）、release projection（发布投影）、OpenSpec（开放规格）和测试引用。
6. 运行 fast verify（快速验证）、full verify（完整验证）和 OpenSpec（开放规格）严格校验。
