# Brainstorm Summary

- Change: add-build-and-verify-init-skill
- Date: 2026-06-26

## 确认的技术方案

新增 `build-and-verify-init`（构建与验证初始化）Skill（技能）作为独立初始化向导入口，现有 `build-and-verify`（构建与验证）Skill（技能）继续作为运行入口。首版只实现轻量 Skill（技能）和 reference（参考文件），不新增脚本，不改变命令行 `init`（初始化）。

`build-and-verify-init`（构建与验证初始化）必须采用 progressive disclosure（渐进式披露）：

- `SKILL.md`（技能说明）保留流程总控和硬规则。
- `references/questionnaire.md`（问答模板）固定问题、选项、后果说明和跳转规则。
- `references/ecosystem-detection.md`（生态识别规则）限定 Node（节点运行时）和 Python（Python 语言）识别。
- `references/config-draft.md`（配置草案规则）定义 checks（检查项）、paths（受影响路径）、inputs（缓存输入）、并行和超时草案规则。
- `references/validation.md`（校验规则）定义配置结构校验、定向依赖检查和用户选择范围的 dry run（试运行）。

## 关键取舍与风险

- 独立 Skill（技能）优先于扩展现有 Skill（技能），以保持运行入口简洁，并提高初始化场景触发精度。
- 首版不新增脚本，降低实现面，但需要用模板完整性测试约束 agent（代理）执行。
- 固定问答模板牺牲灵活度，换取可复用、可审查和可测试。
- 首版只识别 Node（节点运行时）和 Python（Python 语言），其他生态回落为用户手动提供命令。
- 覆盖已有配置允许继续，但必须确认、备份并报告备份路径。
- dry run（试运行）只使用现有 `build`（构建检查）、默认 `verify`（快速验证）和显式 `verify --full`（完整验证）命令范围，不新增单个 check（检查项）运行能力。
- 定向依赖检查在最终写入确认前执行；配置结构校验和 dry run（试运行）在写入后执行。

## 测试策略

- 更新包结构测试，确认 `build-and-verify`（构建与验证）和 `build-and-verify-init`（构建与验证初始化）两个 Skill（技能）入口都存在。
- 保留命令行 `init`（初始化）行为测试，确认仍生成空模板，不做交互式行为。
- 新增 reference（参考文件）完整性测试，覆盖 11 个固定问答、Node/Python 识别、未识别生态回退、默认字符串 command（命令）、配置草案、备份规则、写入前定向依赖检查和用户选择现有命令范围的 dry run（试运行）。
- 运行 OpenSpec（开放规格）严格校验和默认 `verify`（快速验证），不默认运行 `--full`（完整验证）。

## Spec Patch

无。OpenSpec delta spec（规格增量）已包含当前设计确认的需求，不需要额外补丁。
