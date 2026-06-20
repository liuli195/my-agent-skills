## Context

本仓库维护 Agent Plugin（代理插件）和 Skill（技能）源码，没有传统编译产物。当前 `.comet/config.yaml` 没有 `build_command`（构建命令）和 `verify_command`（验证命令），而 `.comet/build-check.sh` 只是历史上为跑通流程留下的项目脚本，且只跑部分 pytest（Python 测试框架）文件。

Comet（双星流程）的 build guard（构建守卫）需要 build 或测试命令通过后才能推进。为了不修改 Comet 本身，仓库应提供一个本地、可重复、无外部副作用的构建命令。

## Goals / Non-Goals

**Goals:**

- 定义 `build_command` 为“本地插件包成型检查”，不是传统编译。
- 让 `build_command` 同时覆盖第一批和第二批检查：Claude（Claude 编码工具）本地校验、Claude marketplace（插件市场目录）结构、Codex（OpenAI 编码代理）插件清单、release-flow projection（发布流程投影）一致性、Guard Profile（守卫画像）模板镜像一致性。
- 定义 `verify_command` 为完整 Python（Python 语言）测试入口。
- 用标准 Python 项目结构承载验证配置。

**Non-Goals:**

- 不修改 Comet 自身流程、脚本或产物。
- 不启用 `claude plugin validate --strict`（严格校验），因为当前仓库已有 warning（警告）会导致严格模式失败。
- 不访问 GitHub（代码托管平台）远端状态，不做发布、安装或用户目录写入。
- 不把深层文档语义判断放进 build。
- 不把完整 pytest 回归放进 build，完整测试属于 verify。

## Decisions

### 1. 使用统一本地检查入口

新增 `scripts/check.py`，提供：

- `python scripts/check.py build`
- `python scripts/check.py verify`

`build` 只做本地结构和一致性检查；`verify` 调用完整测试。这样 Comet 配置、开发者本地命令和后续扩展都使用同一个入口。

备选方案是直接在 `.comet/config.yaml` 写多条 shell 命令。这个方案在 Windows（微软系统）和 Git Bash（Git 命令行环境）之间更脆弱，也不利于输出清晰错误。

### 2. Claude 本地校验进入 build，但不启用 strict

`build` 必须执行：

- `claude plugin validate .`
- 对 `.claude-plugin/marketplace.json` 中每个本地 `plugins[].source` 执行 `claude plugin validate <source>`

当前非 strict 模式能通过，strict 模式会因为现有 warning 失败。strict 清理应作为后续独立工作，而不是本次 build 命令上线的前置条件。

### 3. build 自己补充仓库特有检查

Claude 校验只覆盖 Claude 插件视角，本仓库还需要补充：

- marketplace（插件市场目录）中的插件名称必须和对应 `.claude-plugin/plugin.json` 的 `name` 一致。
- 本地 `source` 必须是仓库内相对路径，不能越出仓库。
- 每个插件必须有 `.claude-plugin/plugin.json` 和 `.codex-plugin/plugin.json`。
- Codex plugin manifest（Codex 插件清单）必须有 `name`、`version`、`description`、`skills` 等关键字段；声明的路径必须存在。
- `.release-flow/projection.yaml` 中 codex-marketplace（Codex 插件市场）生成器列出的插件，必须和 `.claude-plugin/marketplace.json` 中的本地插件集合一致。
- `plugins/agent-guard/assets/templates/guard-profile/` 和 `plugins/agent-guard/skills/agent-guard/assets/templates/guard-profile/` 中的模板镜像必须一致。

### 4. verify 使用标准 Python 测试入口

新增 `pyproject.toml` 的 pytest（Python 测试框架）配置：

- `testpaths = ["tests"]`
- `python_files = ["test_*.py"]`
- `addopts = "-q"`

`python scripts/check.py verify` 运行 `python -m pytest`，由 pytest 配置决定默认范围。这样 `.comet/build-check.sh` 中硬编码的部分测试列表不再作为正式验证入口。

### 5. Comet 配置只指向仓库入口

`.comet/config.yaml` 增加：

```yaml
build_command: python scripts/check.py build
verify_command: python scripts/check.py verify
```

`.comet/build-check.sh` 不再被正式配置引用。是否删除该脚本由任务执行阶段按引用检查结果处理；如果没有引用，应删除，避免误导。

## Risks / Trade-offs

- Claude CLI（Claude 命令行工具）缺失会导致 build 失败。缓解：错误信息明确提示需要安装或启用 Claude CLI。
- 非 strict 校验允许现有 warning 保留。缓解：把 strict 清理作为后续独立工作，不混入本次。
- Guard Profile 模板镜像检查会让双路径模板维护更严格。缓解：只检查字节级一致性，不判断语义。
- `verify` 运行完整 pytest 可能比旧 `.comet/build-check.sh` 更慢。缓解：verify 本来就是完整验证阶段，build 保持轻量。
