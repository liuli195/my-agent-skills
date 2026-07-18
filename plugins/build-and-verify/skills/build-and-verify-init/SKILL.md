---
name: build-and-verify-init
description: Build and Verify（构建与验证）对话式初始化向导；为目标仓库生成 .build-and-verify/config.json（配置文件）草案
---

# Build and Verify Init（构建与验证初始化）

Use this skill when the user asks to initialize（初始化）, generate（生成）, draft（草拟）, or configure（配置） `.build-and-verify/config.json`（配置文件） for a target repository（目标仓库）.

## Hard Boundaries（硬边界）

- 不新增命令行初始化脚本；最终写入必须调用 `build-and-verify`（构建与验证）现有 `scripts/build_and_verify.py init --config --overwrite`（初始化覆盖命令），由 runtime（运行时）负责配置写入、备份、`.gitignore`（忽略规则）合并、runtime（运行时）复制和 cache（缓存）创建。
- 不安装依赖，不写用户级配置，不配置 CI（持续集成）。
- 不修改 runner（运行器）语义。
- 用户沉默不能视为确认。
- 覆盖已有 `.build-and-verify/config.json`（配置文件）前必须展示摘要、等待明确确认并备份。
- 处理依赖或环境问题前必须获得用户明确授权。

## Closed Loop（闭环）

交互式配置、targeted dependency checks（定向依赖检查）、environment checks（环境检查）和 config validation（配置校验）必须在插件内完成。不得把交互式配置、config validation（配置校验）、targeted dependency checks（定向依赖检查）或 environment checks（环境检查）外包给 OpenSpec（开放规格）、测试文件或仓库外说明。闭环只依赖本 skill（技能）和 `references/`（参考文件）：

- `references/questionnaire.md`（问答模板）定义固定交互式配置流程。
- `references/ecosystem-detection.md`（生态识别规则）定义扫描边界、生态候选、通用候选和候选分类。
- `references/config-draft.md`（配置草案规则）定义配置草案结构。
- `references/validation.md`（校验规则）定义写入前依赖和环境检查、备份、写入后 config（配置）结构校验。

## Required Flow（必需流程）

1. 读取 `references/questionnaire.md`（问答模板），按固定问题、选项、后果和跳转推进。
2. 用户允许扫描后，读取 `references/ecosystem-detection.md`（生态识别规则），识别已有配置、Node（节点运行时）、Python（Python 语言）和通用候选；无候选时走手动命令分支。
3. 生成草案前，读取 `references/config-draft.md`（配置草案规则），生成 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）；只有用户确认正整数后才写入可选 `verify.fullBudgetSeconds`（完整验证预算秒数），未启用时省略。
4. inputs（缓存输入）默认由 agent（代理）根据 paths（受影响路径）和 command（命令）来源推导，并在最终写入确认摘要中展示。
5. 覆盖已有配置时自动使用 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件），不单独询问备份路径。
6. 最终写入确认前，读取 `references/validation.md`（校验规则），执行 targeted dependency checks（定向依赖检查）和 environment checks（环境检查），展示问题、影响和建议。
7. 最终写入时，先把用户确认的草案保存为临时 confirmed config（已确认配置），再调用 `python <build-and-verify-script> init --project <repo> --config <confirmed-config> --overwrite`（初始化覆盖命令）。不得由 agent（代理）直接写 `.build-and-verify/config.json`（配置文件）。
8. 写入后按 `references/validation.md`（校验规则）执行 config（配置）结构校验。

## Output（输出）

- 写入前输出候选 checks（检查项）、`paths`（受影响路径）、自动推导的 `inputs`（缓存输入）、运行参数、完整验证预算的最终值或未启用、覆盖摘要、默认备份路径、targeted dependency checks（定向依赖检查）结果和 environment checks（环境检查）结果。超预算只警告并记录报告，不阻断功能验证。
- 写入后输出配置路径、备份路径和 config（配置）结构校验结果；依赖或环境问题只能在用户明确授权后处理。
