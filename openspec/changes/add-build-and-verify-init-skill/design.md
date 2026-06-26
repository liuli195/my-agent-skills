## Context

`build-and-verify`（构建与验证）已经提供可复用的 `build`（构建检查）、默认 `verify`（快速验证）、显式 `verify --full`（完整验证）和命令行 `init`（初始化）。当前 `init`（初始化）只复制空模板，符合“不内置仓库业务逻辑”的边界，但通用仓库接入时仍需要人工设计 `.build-and-verify/config.json`（配置文件）。

本次变更的核心不是扩展 runner（运行器）或命令行，而是新增一个 `agent`（代理）可执行的固定初始化流程。该流程必须减少自由发挥：问题、选项、跳转、配置草案和校验规则都应写入 `Skill`（技能）参考文件。

## Goals / Non-Goals

**Goals:**

- 新增 `build-and-verify-init`（构建与验证初始化）`Skill`（技能），专门承载对话式初始化向导。
- 使用 progressive disclosure（渐进式披露）拆分固定问答模板、生态识别、配置草案和校验规则。
- 首版支持 Node（节点运行时）和 Python（Python 语言）识别，并让用户选择纳入哪些 `check`（检查项）。
- 支持覆盖已有配置，但覆盖前必须确认、备份并更新 `.gitignore`（忽略规则）。
- 写入前必须完成定向依赖检查并展示结果；写入后必须执行配置结构校验和用户选择范围的 `dry run`（试运行）。
- 保留现有命令行 `init`（初始化）空模板行为。

**Non-Goals:**

- 不新增配置生成脚本。
- 不修改 `build_and_verify.py`（构建与验证脚本）或 runner（运行器）执行语义。
- 不安装依赖，不修改用户级配置，不配置 CI（持续集成）。
- 不扩展 Go（Go 语言）、Rust（Rust 语言）、Java（Java 语言）或 .NET（微软开发平台）识别。
- 不默认运行 `verify --full`（完整验证）。

## Decisions

### 1. 新增独立 `build-and-verify-init`（构建与验证初始化）Skill（技能）

选择独立入口，而不是把全部流程塞进现有 `build-and-verify`（构建与验证）Skill（技能）。

原因：现有 Skill（技能）是运行入口，内容需要保持短而稳定；初始化向导包含固定问答、扫描规则、备份规则和校验规则，天然适合单独入口和渐进式披露。

替代方案：继续使用单一 Skill（技能）。缺点是运行说明和初始化向导会混在一起，降低触发精度，也违背用户要求的渐进式披露。

### 2. 首版只做轻量 Skill（技能），不新增脚本

初始化逻辑由 `agent`（代理）按模板执行，首版不提供确定性生成脚本。

原因：用户明确选择轻量 Skill（技能）；当前需求重点是流程和模板约束，不是新增命令行能力。保留脚本空间也能避免过早固化配置生成器。

替代方案：新增脚本生成、备份和写入配置。缺点是首版实现面扩大，并且会让对话式确认和环境处理变复杂。

### 3. 问答流程模板化

`build-and-verify-init`（构建与验证初始化）必须包含固定 questionnaire（问答模板），每个问题必须有固定选项、后果说明和跳转规则。`agent`（代理）不得临场换问题或省略确认页。

模板至少覆盖：

1. 目标仓库路径确认。
2. 是否允许扫描仓库文件。
3. Node（节点运行时）和 Python（Python 语言）检测结果确认。
4. 选择纳入哪些 `check`（检查项）。
5. 确认 `paths`（受影响路径）。
6. 确认 `inputs`（缓存输入）。
7. 确认并行与超时设置。
8. 已有配置时确认覆盖。
9. 确认备份路径。
10. 选择 `dry run`（试运行）范围。
11. 最终写入确认。

### 4. 生态识别限定在 Node（节点运行时）和 Python（Python 语言）

Node（节点运行时）识别优先读取 `package.json`（包配置）的 `scripts`（脚本），并识别 build、test、lint、typecheck 等常见脚本。`check`（检查脚本）和 `verify`（验证脚本）必须映射为不同 check id（检查项标识），避免同组 id（标识）重复。

Python（Python 语言）识别优先读取 `pyproject.toml`（项目配置）、`pytest.ini`（测试配置）、`tox.ini`（测试环境配置）、`noxfile.py`（任务配置）和 `requirements*.txt`（依赖清单），优先建议 pytest（Python 测试运行器）和现有脚本。

如果同时检测到两类生态，全部展示并让用户选择。

如果未识别 Node（节点运行时）或 Python（Python 语言）生态，向导仍必须继续固定问答流程：让用户手动提供 build（构建检查）和 verify（验证）命令，再确认 `paths`（受影响路径）、`inputs`（缓存输入）、覆盖备份和试运行范围。

### 5. 配置草案保留现有 build-and-verify（构建与验证）契约

草案默认同时生成 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）。`id`（标识）使用短横线风格，例如 `build.node`、`verify.python-tests`。`command`（命令）默认使用字符串形式，便于用户阅读和编辑；如用户明确需要更稳定的参数边界，`agent`（代理）可说明差异后改用列表形式。

`paths`（受影响路径）和 `inputs`（缓存输入）按生态粗分，且写入配置。`command`（命令）默认使用字符串形式，便于用户阅读和维护；只有用户明确要求更稳定的参数边界时，才允许改用列表形式。`verify.maxParallel`（最大并行检查数）、`verify.timeoutSeconds`（超时秒数）和 `parallel: true`（并行检查）可以生成，但必须逐项解释并让用户确认。并行默认推荐 `auto`（自动）语义；如果底层工具没有 `auto`（自动）语义，不能硬编。

### 6. 覆盖配置必须备份

如果目标仓库已存在 `.build-and-verify/config.json`（配置文件），向导允许覆盖，但必须先展示覆盖摘要并获得明确确认。

覆盖前旧配置必须备份到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件）。向导还必须确保 `.build-and-verify/.gitignore`（忽略规则）包含 `/backups/`。

### 7. 校验采用定向依赖检查

向导不做泛化依赖扫描，只根据草案中的明显特征检查。定向依赖检查必须在最终写入确认前执行，这样用户能在已知问题的前提下决定是否仍然写入：

- 命令里有 `pytest -n` 或 `--numprocesses` 时，检查 `pytest-xdist`（Pytest 并行插件）是否可用。
- 命令调用外部可执行文件时，检查入口是否可找到。
- `paths`（受影响路径）和 `inputs`（缓存输入）指向不存在文件或目录时，提示用户确认。
- `parallel: true`（并行检查）只说明由 build-and-verify（构建与验证）runner（运行器）支持，不推断业务依赖。

发现依赖或环境问题时仍允许写入配置，但必须列出问题、影响和建议。只有用户明确授权时，`agent`（代理）才处理依赖或环境问题。

写入后再执行配置结构校验和用户选择范围的试运行。

dry run（试运行）不新增 runner（运行器）能力，也不支持单独运行某一个 check（检查项）。用户只能在现有公开命令范围内选择：

- 只运行 `build`（构建检查）。
- 只运行默认 `verify`（快速验证）。
- 运行 `build`（构建检查）和默认 `verify`（快速验证）。
- 明确选择后运行 `verify --full`（完整验证）。

完成初始化前必须选择并执行一个 dry run（试运行）范围；不能把“只做配置结构校验”作为完成选项。

如用户需要单个 check（检查项）级别的试运行，本 change（变更）只要求向导说明当前 runner（运行器）不支持该粒度，并建议用户选择最接近的现有命令范围。

## Risks / Trade-offs

- [Risk] 轻量 Skill（技能）依赖 `agent`（代理）按模板执行，仍可能漏步骤。Mitigation: 用测试检查 reference（参考文件）存在、关键问题存在、确认页和校验规则不可缺。
- [Risk] 只支持 Node（节点运行时）和 Python（Python 语言）会漏掉其他仓库。Mitigation: 明确首版范围，未识别生态时回到用户手动选择命令。
- [Risk] 覆盖已有配置可能丢失用户手写规则。Mitigation: 强制确认和时间戳备份，并默认忽略备份目录。
- [Risk] 定向依赖检查不等于真实环境完全可用。Mitigation: 写入后提供用户选择的 `dry run`（试运行），并把问题作为报告输出。

## Migration Plan

1. 更新 `test-framework-plugin`（测试框架插件）delta spec（规格增量），把单一 Skill（技能）入口改为运行入口和初始化向导入口。
2. 新增 `build-and-verify-init`（构建与验证初始化）Skill（技能）及参考文件。
3. 更新插件 package（包）测试，确认两个 Skill（技能）入口存在，现有命令行 `init`（初始化）仍保持空模板行为。
4. 新增模板完整性测试，确认固定问答、覆盖备份、定向依赖检查和 `dry run`（试运行）选择规则存在。

Rollback（回滚）方式：删除新增 `build-and-verify-init`（构建与验证初始化）Skill（技能）和相关测试，并恢复规格中的单一 Skill（技能）入口要求。命令行行为未改变，无目标仓库迁移成本。

## Open Questions

None.
