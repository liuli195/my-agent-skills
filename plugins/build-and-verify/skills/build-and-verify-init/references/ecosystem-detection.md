# Ecosystem Detection（生态识别）

识别已有配置、Node（节点运行时）、Python（Python 语言）和 Generic Candidate Discovery（通用候选发现）。混合仓库必须同时展示多类候选 checks（检查项），不得自动裁决优先级。

## Scan Boundary（扫描边界）

- 只在用户授权扫描后读取目标仓库文件。
- 不安装依赖，不运行 package manager（包管理器），不修改文件，只读取本文件列出的信号。
- 不得运行候选 command（命令）；候选 command（命令）只用于展示、分类、依赖检查和最终配置草案。

## Existing Configuration（已有配置）

- 信号：`.build-and-verify/config.json`（配置文件）存在。
- 读取已有 `build.checks`（构建检查项）和 `verify.checks`（验证检查项），逐项保留 check id（检查项标识）、command（命令）、paths（受影响路径）、inputs（缓存输入）、parallel（并行检查）和 timeoutSeconds（超时秒数）。
- confidence（置信度）为 High（高），risk（风险提示）为“来自已有配置，覆盖前必须备份并确认”。
- 已有配置无法解析为 JSON（JSON 配置格式）时，不得猜测内容；报告问题并继续其他候选扫描。
- 展示 source（来源）、check id（检查项标识）、command（命令）、分组、confidence（置信度）、reason（纳入理由）和 risk（风险提示）。

## Node（节点运行时）

- 信号：`package.json`（包配置）存在。
- 读取 `package.json`（包配置）的 `scripts`（脚本）对象。
- 识别 `build`、`test`、`lint`、`typecheck`、`check`、`verify` 等 scripts（脚本）名。
- 用包管理器命令展示候选 command（命令）。如果存在 lockfile（锁文件），按下列顺序建议：
  - `pnpm-lock.yaml` -> `pnpm <script>`
  - `yarn.lock` -> `yarn <script>`
  - `package-lock.json` -> `npm run <script>`
  - 无 lockfile（锁文件） -> `npm run <script>`
- 只使用第一个匹配的 lockfile（锁文件）选择包管理器；如果多个 lockfile（锁文件）同时存在，必须展示冲突并让用户选择一个包管理器，不得同时生成多个互相冲突的 command（命令）。

候选映射：

- `build` -> `build.node`
- `test` -> `verify.node-tests`
- `lint` -> `verify.node-lint`
- `typecheck` -> `verify.node-typecheck`
- `check` -> `verify.node-check`
- `verify` -> `verify.node-verify`

如果候选脚本名导致同一分组内 check id（检查项标识）冲突，agent（代理）必须在展示草案前改成唯一 id（标识），并向用户说明改名原因。

展示要求：

- 展示脚本名、原始 script（脚本）内容、建议 check id（检查项标识）和建议 command（命令）。
- 等待用户选择纳入哪些 checks（检查项）。

## Python（Python 语言）

信号：

- `pyproject.toml`（项目配置）
- `pytest.ini`（测试配置）
- `tox.ini`（测试环境配置）
- `noxfile.py`（任务配置）
- `requirements*.txt`（依赖清单）

- 优先识别 pytest（Python 测试运行器）：存在 `pytest.ini`（测试配置）、`pyproject.toml`（项目配置）中包含 pytest（Python 测试运行器）配置、或 `requirements*.txt`（依赖清单）包含 `pytest`。
- 如果存在 `tox.ini`（测试环境配置），展示 `tox`（测试环境工具）候选，但不替代 pytest（Python 测试运行器）候选。
- 如果存在 `noxfile.py`（任务配置），展示 `nox`（自动化任务工具）候选，但不替代 pytest（Python 测试运行器）候选。

候选映射：

- pytest（Python 测试运行器） -> `verify.python-tests`，默认 command（命令）为 `python -m pytest`
- tox（测试环境工具） -> `verify.python-tox`，默认 command（命令）为 `tox`
- nox（自动化任务工具） -> `verify.python-nox`，默认 command（命令）为 `nox`

展示要求：

- 展示检测到的配置文件、建议 check id（检查项标识）和建议 command（命令）。
- 等待用户选择纳入哪些 checks（检查项）。

## Generic Candidate Discovery（通用候选发现）

通用候选发现用于没有已有配置或生态候选过少的仓库。agent（代理）只能按本节分类；不得自由编造扫描范围、不得运行候选 command（命令），不得把高风险候选默认纳入。

扫描信号：

- `package.json`（包配置）的 `scripts`（脚本）对象。
- `pyproject.toml`（项目配置）、`pytest.ini`（测试配置）、`tox.ini`（测试环境配置）、`noxfile.py`（任务配置）和 `requirements*.txt`（依赖清单）。
- `Makefile`（任务文件）；展示时称为 Makefile（任务文件）候选。
- `scripts/`（脚本目录）下名称包含 `build`（构建）、`check`（检查）、`test`（测试）、`verify`（验证）、`lint`（代码检查）或 `package`（打包）的文件。
- `tests/`（测试目录）存在。
- `openspec/`（开放规格目录）存在。

输出字段：

- source（来源）：候选来自哪个文件、脚本名、配置项或目录。
- check id（检查项标识）：建议写入配置的 id（标识）。
- command（命令）：建议写入配置的命令；不得运行。
- section（分组）：`build`（构建检查）或 `verify`（验证）。
- confidence（置信度）：High（高）、Medium（中）或 Low（低）。
- reason（纳入理由）：为什么该候选适合成为 check（检查项）。
- risk（风险提示）：可能修改外部状态、运行过慢或分类不确定时必须说明。

分类规则：

- 名称或脚本内容明确是 build（构建）或 package（打包），且不包含风险词时，归类为 `build`（构建检查）。
- 名称或脚本内容明确是 test（测试）、check（检查）、verify（验证）、lint（代码检查）、typecheck（类型检查）、pytest（Python 测试运行器）、tox（测试环境工具）、nox（自动化任务工具）或 openspec validate（开放规格校验）时，归类为 `verify`（验证）。
- `tests/`（测试目录）存在且检测到 Python（Python 语言）测试依赖时，可以生成 `verify.python-tests`（Python 测试检查），默认 command（命令）为 `python -m pytest`。
- `openspec/`（开放规格目录）存在时，可以生成 `verify.openspec`（开放规格验证），默认 command（命令）为 `openspec validate --all --strict --no-interactive`，但必须通过 targeted dependency checks（定向依赖检查）报告 `openspec`（开放规格工具）是否可发现。
- 多个候选映射到同一 check id（检查项标识）时，必须改成唯一 id（标识）并说明改名原因。

confidence（置信度）规则：

- High（高）：来源是明确的测试、构建、检查或校验入口，且 command（命令）不包含风险词。
- Medium（中）：来源名称相关，但用途需要用户确认，例如自定义脚本、Makefile（任务文件）目标或泛化 check（检查）命令。
- Low（低）：来源只弱相关、分类不确定，或可能很慢、覆盖面不清。

risk（风险提示）降级规则：

- command（命令）或脚本名包含 deploy（部署）、publish（发布）、release（发布流程）、push（推送）、delete（删除）、remove（移除）或 migrate（迁移）时，必须标记 risk（风险提示）。
- 风险候选不得默认纳入；只能展示给用户选择，或建议用户手动新增更安全的 command（命令）。
- 任何明显修改外部环境、远端状态或数据状态的候选都必须降级为 Low（低）或排除。

展示要求：

- 展示所有 High（高）候选。
- Medium（中）和 Low（低）候选必须单独列出，并说明默认不会纳入。
- 每个候选必须展示 source（来源）、check id（检查项标识）、command（命令）、section（分组）、confidence（置信度）、reason（纳入理由）和 risk（风险提示）。

## Mixed Repository（混合仓库）

- Node（节点运行时）、Python（Python 语言）和通用候选信号同时存在时，同时展示多类候选 checks（检查项）。
- Node（节点运行时）和 Python（Python 语言）信号同时存在时，仍必须同时展示两类候选 checks（检查项）；通用候选只作为额外候选来源。
- 不根据文件数量、语言比例或 agent（代理）偏好自动删减候选项。
- 由用户选择纳入哪些 checks（检查项）。

## 未识别生态

没有识别到已有配置、Node（节点运行时）、Python（Python 语言）或通用候选信号时：

- 继续使用 questionnaire（问答模板）。
- 让用户手动提供 build（构建检查）和 verify（验证）命令。
- 继续确认 paths（受影响路径）和运行参数；inputs（缓存输入）由 agent（代理）自动推导并在最终摘要展示；覆盖已有配置时自动使用默认备份路径并执行 config validation（配置校验）。
