---
name: build-and-verify-init
description: Build and Verify（构建与验证）对话式初始化向导；为目标仓库生成 .build-and-verify/config.json（配置文件）草案
---

# Build and Verify Init（构建与验证初始化）

Use this skill when the user asks to initialize（初始化）, generate（生成）, draft（草拟）, or configure（配置） `.build-and-verify/config.json`（配置文件） for a target repository（目标仓库）.

## Hard Boundaries（硬边界）

- 不新增命令行初始化脚本；`build-and-verify`（构建与验证）现有 `scripts/build_and_verify.py init`（初始化命令）仍只写空模板。
- 不安装依赖。
- 不写用户级配置。
- 不配置 CI（持续集成）。
- 不修改 runner（运行器）语义。
- 不把用户沉默视为确认；用户沉默不能视为确认。
- 覆盖已有 `.build-and-verify/config.json`（配置文件）前必须展示摘要、等待明确确认并备份。
- 处理依赖或环境问题前必须获得用户明确授权。

## Required Flow（必需流程）

1. 先读取 `references/questionnaire.md`（问答模板），并按固定问题、固定选项、选择后果和跳转规则推进。
2. 用户允许扫描后，读取 `references/ecosystem-detection.md`（生态识别规则），只识别 Node（节点运行时）和 Python（Python 语言）；未识别时走手动命令分支。
3. 生成草案前，读取 `references/config-draft.md`（配置草案规则），按其中规则生成 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）。
4. 最终写入确认前，读取 `references/validation.md`（校验规则），执行 targeted dependency checks（定向依赖检查）并展示问题、影响和建议。
5. 写入后按 `references/validation.md`（校验规则）执行 config（配置）结构校验和用户选择范围的 dry run（试运行）。

## Output（输出）

- 写入前输出候选 checks（检查项）、`paths`（受影响路径）、`inputs`（缓存输入）、运行参数、覆盖摘要、备份路径和定向依赖检查结果。
- 写入后输出配置路径、备份路径、结构校验结果和 dry run（试运行）结果。
- 如果用户要求单独运行某个 check（检查项），说明当前 runner（运行器）不支持该粒度，并建议选择现有 `build`（构建检查）、默认 `verify`（快速验证）或显式 `verify --full`（完整验证）范围。
