# Config Draft（配置草案）

本文件定义 `.build-and-verify/config.json`（配置文件）草案生成规则。草案必须可审查，写入前必须展示给用户确认。

## Shape（结构）

草案默认使用：

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
- command（命令）默认使用字符串形式，便于用户阅读和维护。
- 列表形式 command（命令）只在用户明确要求更稳定参数边界时使用。

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
- 用户可以移除 paths（受影响路径），使该 verify check（验证检查项）成为 global check（全局检查项）。

## inputs（缓存输入）

- 每个 check（检查项）都应建议 inputs（缓存输入），以降低 cache key（缓存键）不稳定风险。
- 写入前必须逐项展示 inputs（缓存输入）并等待用户确认。
- 指向不存在文件或目录时，在 validation（校验）阶段提示用户确认。

## Runtime Tuning（运行参数）

- `verify.maxParallel`（最大并行检查数）只能在解释含义并获得用户确认后写入。
- `verify.timeoutSeconds`（超时秒数）只能在解释含义并获得用户确认后写入。
- `parallel: true`（并行检查）只能在解释 runner（运行器）并行语义并获得用户确认后写入。
- 并行默认推荐 auto（自动）语义；如果某个工具没有 auto（自动）语义，不能硬编码 auto（自动）参数。
