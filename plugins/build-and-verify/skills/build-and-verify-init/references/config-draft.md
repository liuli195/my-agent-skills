# Config Draft（配置草案）

定义 `.build-and-verify/config.json`（配置文件）草案规则。草案必须可审查，写入前必须展示给用户确认。

## Shape（结构）

默认结构：

```json
{
  "version": 1,
  "build": {
    "checks": []
  },
  "verify": {
    "checks": []
  }
}
```

## Checks（检查项）

- 必须同时支持 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）。
- check id（检查项标识）使用短横线风格，例如 `build.node`、`verify.node-tests`、`verify.python-tests`。
- 同一分组内 check id（检查项标识）必须唯一。
- command（命令）默认使用字符串形式，便于阅读和维护。
- 列表形式 command（命令）只在用户明确要求更稳定参数边界时使用。
- 高置信度候选可以默认建议纳入，但仍必须展示给用户确认。
- 中低置信度候选只能展示给用户选择，用户未明确选择时不得写入配置草案。
- 风险候选不得默认纳入；如果用户明确选择，草案摘要必须保留 risk（风险提示）和建议。

## Existing Configuration（已有配置）

- 已有 `.build-and-verify/config.json`（配置文件）候选尽量原样保留。
- 保留 check id（检查项标识）、command（命令）、paths（受影响路径）、inputs（缓存输入）、checkParallel（检查项间并行）、pytestXdistWorkers（Pytest 工作进程数）和 timeoutSeconds（超时秒数），以及已有 `verify.fullBudgetSeconds`（完整验证预算秒数）。
- 已有配置含旧 `parallel`（旧并行字段）时，必须提示用户迁移为 `checkParallel`（检查项间并行），不得写入新草案。
- 覆盖前展示覆盖摘要、自动生成的备份路径和最终写入确认。

## Generic Candidates（通用候选）

- `build.<name>`
  - command（命令）: 来自明确 build（构建）或 package（打包）入口。
  - inputs（缓存输入）: 来源脚本、配置文件和主要源码目录。
- `verify.<name>`
  - command（命令）: 来自明确 test（测试）、check（检查）、verify（验证）、lint（代码检查）、typecheck（类型检查）或 validate（校验）入口。
  - paths（受影响路径）: 与来源脚本、测试目录、配置文件和主要源码目录相关的路径。
  - inputs（缓存输入）: 来源脚本、配置文件、依赖清单和测试目录。
- 中低置信度通用候选必须先由用户确认是否纳入，再根据来源补齐 paths（受影响路径）和 inputs（缓存输入）。

## Node（节点运行时）建议

- `build.node`
  - command（命令）: `npm run build`、`pnpm build` 或 `yarn build`
  - inputs（缓存输入）: `package.json`、lockfile（锁文件）、源码目录
- `verify.node-tests`
  - command（命令）: `npm test`、`pnpm test` 或 `yarn test`
  - paths（受影响路径）: `src/**`、`test/**`、`tests/**`、`package.json`
  - inputs（缓存输入）: `package.json`、lockfile（锁文件）、源码目录、测试目录
- `verify.node-lint`
  - command（命令）: `npm run lint`、`pnpm lint` 或 `yarn lint`
  - paths（受影响路径）: `src/**`、配置文件和脚本文件
  - inputs（缓存输入）: `package.json`、lockfile（锁文件）、lint（代码检查）配置
- `verify.node-typecheck`
  - command（命令）: `npm run typecheck`、`pnpm typecheck` 或 `yarn typecheck`
  - paths（受影响路径）: `src/**`、`tsconfig.json`
  - inputs（缓存输入）: `package.json`、lockfile（锁文件）、`tsconfig.json`、源码目录

## Python（Python 语言）建议

- `verify.python-tests`
  - command（命令）: `python -m pytest`
  - paths（受影响路径）: `src/**`、`tests/**`、`pyproject.toml`、`pytest.ini`
  - inputs（缓存输入）: `pyproject.toml`、`pytest.ini`、`requirements*.txt`、源码目录、测试目录
- `verify.python-tox`
  - command（命令）: `tox`
  - paths（受影响路径）: `src/**`、`tests/**`、`tox.ini`
  - inputs（缓存输入）: `tox.ini`、`pyproject.toml`、`requirements*.txt`、源码目录、测试目录
- `verify.python-nox`
  - command（命令）: `nox`
  - paths（受影响路径）: `src/**`、`tests/**`、`noxfile.py`
  - inputs（缓存输入）: `noxfile.py`、`pyproject.toml`、`requirements*.txt`、源码目录、测试目录

## paths（受影响路径）

- verify checks（验证检查项）应建议 paths（受影响路径）。
- 写入前必须逐项展示 paths（受影响路径）并等待用户确认。
- 用户可移除 paths（受影响路径），使该 verify check（验证检查项）成为 global check（全局检查项）。

## inputs（缓存输入）

- inputs（缓存输入）默认从 paths（受影响路径）和 command（命令）来源推导，降低 cache key（缓存键）不稳定风险。
- 写入前在 Q6 摘要中展示 inputs（缓存输入），但不单独提问。
- 用户选择返回前面问题修改草案时，才修改 inputs（缓存输入）。
- 指向不存在文件或目录时，在 validation（校验）阶段提示用户确认。

## Runtime Tuning（运行参数）

- `verify.maxParallel`（最大并行检查数）只能在解释含义并获得用户确认后写入。
- `verify.timeoutSeconds`（超时秒数）只能在解释含义并获得用户确认后写入。
- `verify.fullBudgetSeconds`（完整验证预算秒数）只能在说明超预算只警告并记录报告后、用户确认正整数后写入；未启用时省略。
- `checkParallel: true`（检查项间并行）只能在解释 runner（运行器）并行语义并获得用户确认后写入。
- `pytestXdistWorkers`（Pytest 工作进程数）只能在 command（命令）是 pytest（Python 测试框架）命令、解释 pytest-xdist（Pytest 并行插件）依赖并获得用户确认后写入；值只能是 `"auto"`（自动）或正整数。
- `parallel`（旧并行字段）不得写入新草案；已有配置含该字段时，必须提示用户重新确认并迁移为 `checkParallel`（检查项间并行）。
- 并行默认推荐 auto（自动）语义；如果某个工具没有 auto（自动）语义，不能硬编码 auto（自动）参数。
