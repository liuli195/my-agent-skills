# Ecosystem Detection（生态识别）

本文件只允许识别 Node（节点运行时）和 Python（Python 语言）。混合仓库必须同时展示两类候选 checks（检查项），不得自动裁决优先级。

## Scan Boundary（扫描边界）

- 只在用户授权扫描后读取目标仓库文件。
- 不安装依赖，不运行 package manager（包管理器），不修改文件。
- 只读取本文件列出的生态信号。

## Node（节点运行时）

检测信号：

- `package.json`（包配置）存在。

读取规则：

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

检测信号：

- `pyproject.toml`（项目配置）
- `pytest.ini`（测试配置）
- `tox.ini`（测试环境配置）
- `noxfile.py`（任务配置）
- `requirements*.txt`（依赖清单）

读取规则：

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

## Mixed Repository（混合仓库）

- Node（节点运行时）和 Python（Python 语言）信号同时存在时，同时展示两类候选 checks（检查项）。
- 不根据文件数量、语言比例或 agent（代理）偏好自动删减候选项。
- 由用户选择纳入哪些 checks（检查项）。

## 未识别生态

如果没有识别到 Node（节点运行时）或 Python（Python 语言）信号：

- 继续使用 questionnaire（问答模板）。
- 让用户手动提供 build（构建检查）和 verify（验证）命令。
- 继续确认 paths（受影响路径）、inputs（缓存输入）、覆盖备份和 dry run（试运行）范围。
