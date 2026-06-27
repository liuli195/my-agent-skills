---
comet_change: add-build-and-verify-init-skill
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-26-add-build-and-verify-init-skill
status: final
---

# Build and Verify Init Skill Design

## 背景

`build-and-verify`（构建与验证）已经提供统一运行入口：`build`（构建检查）、默认 `verify`（快速验证）和显式 `verify --full`（完整验证）。现有命令行 `init`（初始化）只复制空模板，这符合“不内置仓库业务逻辑”的边界，但通用仓库首次接入仍要手写 `.build-and-verify/config.json`（配置文件）。

本次新增 `build-and-verify-init`（构建与验证初始化）Skill（技能），让 agent（代理）按固定模板完成仓库扫描、候选检查项展示、配置草案生成、覆盖确认、备份、依赖/环境检查和配置校验。重点是把初始化对话变成可复用、可审查、可测试的流程，而不是让 agent（代理）临场自由发挥。

## 目标

- 新增独立 `build-and-verify-init`（构建与验证初始化）Skill（技能）作为对话式初始化向导。
- 保持 `build-and-verify`（构建与验证）Skill（技能）作为运行入口。
- 保持命令行 `init`（初始化）行为不变，仍只生成空模板。
- 使用 progressive disclosure（渐进式披露）拆分固定问答、候选识别、配置草案和校验规则。
- 识别已有配置、Node（节点运行时）、Python（Python 语言）和受约束通用候选；不得运行候选 command（命令）。
- 覆盖已有配置前必须确认并备份。
- 写入前必须做定向依赖检查和环境检查并展示结果；写入后必须做配置结构校验。

## 非目标

- 不新增配置生成脚本。
- 不修改 `build_and_verify.py`（构建与验证脚本）或 runner（运行器）执行语义。
- 不自动安装依赖，不修改用户级配置，不配置 CI（持续集成）。
- 不新增 Go（Go 语言）、Rust（Rust 语言）、Java（Java 语言）或 .NET（微软开发平台）专门识别规则；通用候选只按文件、目录、脚本名和命令内容分类。
- 不自动运行 `build`（构建检查）、默认 `verify`（快速验证）或 `verify --full`（完整验证）。

## 技术方案

### Skill（技能）结构

新增目录：

```text
plugins/build-and-verify/skills/build-and-verify-init/
  SKILL.md
  references/
    questionnaire.md
    ecosystem-detection.md
    config-draft.md
    validation.md
```

`SKILL.md`（技能说明）只放入口规则和硬边界，正文保持短。所有细节通过 reference（参考文件）按需加载：

- `questionnaire.md`（问答模板）：固定问题、选项、后果说明和跳转规则。
- `ecosystem-detection.md`（生态识别规则）：已有配置、Node（节点运行时）、Python（Python 语言）和通用候选识别。
- `config-draft.md`（配置草案规则）：check（检查项）命名、command（命令）、paths（受影响路径）、inputs（缓存输入）、并行和超时。
- `validation.md`（校验规则）：配置结构校验、targeted dependency checks（定向依赖检查）和 environment checks（环境检查）。

### 固定问答流程

向导必须按 `questionnaire.md`（问答模板）提问，不允许自由改写流程。模板固定为 6 步：

1. 目标仓库路径确认。
2. 是否允许扫描仓库文件。
3. 候选 checks（检查项）确认：合并检测结果确认和纳入选择。
4. 确认 paths（受影响路径）。
5. 确认并行和超时设置。
6. 覆盖与最终写入确认。

inputs（缓存输入）默认由 agent（代理）从 paths（受影响路径）和 command（命令）来源推导，并在最终摘要中展示。覆盖已有配置时使用默认备份路径 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件），不单独询问备份路径。

每个问题都必须包含固定选项和选择后果。用户沉默不能视为确认。

### 候选识别

已有配置：

- 读取 `.build-and-verify/config.json`（配置文件）中的 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）。
- 原样展示已有 check id（检查项标识）、command（命令）、paths（受影响路径）、inputs（缓存输入）、parallel（并行检查）和 timeoutSeconds（超时秒数）。
- 标记为 High（高）confidence（置信度），覆盖前必须备份并确认。

Node（节点运行时）：

- 读取 `package.json`（包配置）。
- 从 `scripts`（脚本）中识别 build、test、lint、typecheck 等候选命令。
- `check`（检查脚本）和 `verify`（验证脚本）必须映射为不同 check id（检查项标识），例如 `verify.node-check` 和 `verify.node-verify`，避免同组 id（标识）重复。
- 展示候选 checks（检查项），由用户选择写入哪些项。

Python（Python 语言）：

- 读取 `pyproject.toml`（项目配置）、`pytest.ini`（测试配置）、`tox.ini`（测试环境配置）、`noxfile.py`（任务配置）和 `requirements*.txt`（依赖清单）。
- 优先建议 pytest（Python 测试运行器）和项目已有脚本。
- 展示候选 checks（检查项），由用户选择写入哪些项。

通用候选：

- 扫描 `Makefile`（任务文件）、`scripts/`（脚本目录）、`tests/`（测试目录）和 `openspec/`（开放规格目录）等受控信号。
- 对候选输出 source（来源）、check id（检查项标识）、command（命令）、section（分组）、confidence（置信度）、reason（纳入理由）和 risk（风险提示）。
- 不得运行候选 command（命令）。风险候选不得默认纳入。

混合仓库同时展示已有配置、Node（节点运行时）、Python（Python 语言）和通用候选，不做自动优先级裁决。

未识别任何候选时，向导仍继续固定问答流程：让用户手动提供 build（构建检查）和 verify（验证）命令，再确认 paths（受影响路径）和运行参数；inputs（缓存输入）自动推导，覆盖时使用默认备份路径。

### 配置草案

草案默认同时支持：

- `build.checks`（构建检查项）
- `verify.checks`（验证检查项）

check id（检查项标识）使用短横线风格，例如 `build.node`、`verify.node-tests`、`verify.python-tests`。

command（命令）默认使用字符串形式，便于用户阅读和维护。只有用户明确需要更稳定的参数边界时，agent（代理）才说明差异并改用列表形式。

paths（受影响路径）按候选来源建议并单独确认。inputs（缓存输入）由 agent（代理）从 paths（受影响路径）和 command（命令）来源推导，只在最终写入摘要中展示；用户返回修改草案时才调整 inputs（缓存输入）。

运行参数可以生成，但必须解释并确认：

- `verify.maxParallel`（最大并行检查数）
- `verify.timeoutSeconds`（超时秒数）
- `parallel: true`（并行检查）

并行默认推荐 auto（自动）语义；如果某个工具没有 auto（自动）语义，不能硬编码 auto（自动）参数。

### 覆盖和备份

如果 `.build-and-verify/config.json`（配置文件）已存在，向导可以覆盖，但必须先展示覆盖摘要并等待明确确认。

覆盖前必须备份旧配置：

```text
.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json
```

如果 `.build-and-verify/backups`（备份目录）不存在，向导必须先创建该目录。

同时确保 `.build-and-verify/.gitignore`（忽略规则）包含：

```text
/backups/
```

写入结果必须报告备份路径。

### 校验

最终写入确认前必须执行定向依赖检查和环境检查并展示结果。写入后必须执行配置结构校验。

检查顺序：

1. targeted dependency checks（定向依赖检查）：只根据配置草案中的明显特征检查，在写入前完成。
2. environment checks（环境检查）：确认目标仓库路径存在且是目录、配置目录可创建或可写入；覆盖已有配置时确认备份目录可创建且备份路径仍在目标仓库内。
3. config（配置）结构校验：确认 `.build-and-verify/config.json`（配置文件）符合 runner（运行器）契约，在写入后完成。

定向依赖检查规则：

- command（命令）包含 `pytest -n` 或 `--numprocesses` 时，检查 `pytest-xdist`（Pytest 并行插件）是否可用。
- command（命令）调用外部可执行文件时，检查入口是否可找到。
- paths（受影响路径）或 inputs（缓存输入）指向不存在文件或目录时，提示用户确认。
- `parallel: true`（并行检查）只说明 build-and-verify（构建与验证）runner（运行器）支持，不推断业务依赖。

发现依赖或环境问题时，仍允许写入配置，但必须列明问题、影响和建议。只有用户明确授权后，agent（代理）才处理依赖或环境问题。

初始化向导不自动执行仓库检查命令；完成条件只包括配置写入、配置结构校验、依赖/环境问题报告。

## 测试策略

- 更新 package（包）测试：确认插件提供 `build-and-verify`（构建与验证）和 `build-and-verify-init`（构建与验证初始化）两个 Skill（技能）入口。
- 保留命令行 `init`（初始化）测试：确认仍生成空模板、`.gitignore`（忽略规则）和 `cache`（缓存）目录，不执行交互式初始化。
- 新增 reference（参考文件）完整性测试：
  - `questionnaire.md`（问答模板）包含 6 个固定问题、固定选项和最终写入确认。
  - `ecosystem-detection.md`（生态识别规则）覆盖已有配置、Node（节点运行时）、Python（Python 语言）和通用候选检测。
  - `config-draft.md`（配置草案规则）覆盖 check id（检查项标识）、默认字符串 command（命令）、paths（受影响路径）、inputs（缓存输入）、并行和超时确认。
  - `validation.md`（校验规则）覆盖 pytest-xdist（Pytest 并行插件）检查、可执行入口检查、缺失路径提示、环境检查、未授权不安装依赖和配置结构校验。
  - 覆盖备份规则包含 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件）和 `/backups/` 忽略规则。
- 新增模板执行模拟测试：按 reference（参考文件）的关键规则生成配置、备份已有配置、报告定向依赖和环境问题、校验结构，用于证明 6 步模板可以产出符合 runner（运行器）契约的 `.build-and-verify/config.json`（配置文件）。
- `pyproject.toml`（项目配置）允许出现在初始化 reference（参考文件）中作为 Python（Python 语言）生态识别信号；现有运行配置仍通过独立测试保证不会把 `pyproject.toml`（项目配置）重新写入 active config command（现行配置命令）。
- 运行 OpenSpec（开放规格）严格校验。
- 运行默认 `verify`（快速验证），不默认运行 `--full`（完整验证）。

## 风险和缓解

- 风险：轻量 Skill（技能）依赖 agent（代理）按模板执行，仍可能漏步骤。
  缓解：用测试检查 reference（参考文件）存在、关键规则不可缺，并用模板执行模拟覆盖备份、结构校验、定向依赖检查和环境检查主流程。

- 风险：固定问答模板降低灵活度。
  缓解：未识别生态时允许用户手动提供命令，但仍通过模板确认。

- 风险：覆盖已有配置可能丢失手写内容。
  缓解：强制覆盖确认、时间戳备份和结果报告。

- 风险：定向依赖检查不能证明环境完全可用。
  缓解：写入前明确列出依赖和环境问题，并提示用户可授权 agent（代理）协助处理环境和外部依赖问题。

## Spec Patch

无。OpenSpec（开放规格）delta spec（规格增量）已包含本设计需要的行为变更。
