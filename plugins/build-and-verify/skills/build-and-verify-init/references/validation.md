# Validation（校验）

定义写入前后检查顺序。检查发现问题时仍允许用户继续写入配置，但必须列明问题、影响和建议。agent（代理）不安装依赖，不得未经授权安装依赖或修改外部环境。

## Closed Loop（闭环）

validation（校验）必须在 `build-and-verify-init`（构建与验证初始化）插件内完成，不得把校验结果留到插件外部流程补做。写入前摘要必须同时列出 targeted dependency checks（定向依赖检查）结果和 environment checks（环境检查）结果；写入后立即报告 config（配置）结构校验结果。

## Order（顺序）

1. 写入前执行 targeted dependency checks（定向依赖检查）。
2. 写入前执行 environment checks（环境检查）。
3. 用户最终确认后，确保 `.build-and-verify/.gitignore`（忽略规则）包含默认本地目录规则。
4. 必要时备份已有配置。
5. 写入 `.build-and-verify/config.json`（配置文件）。
6. 写入后执行 config（配置）结构校验。

## Targeted Dependency Checks（定向依赖检查）

- command（命令）包含 `pytest -n`、`-n` pytest（Python 测试运行器）参数或 `--numprocesses` 时，检查 `pytest-xdist`（Pytest 并行插件）是否可用。
- command（命令）调用外部可执行入口时，检查该可执行入口是否可找到。
- paths（受影响路径）或 inputs（缓存输入）指向缺失文件或目录时，提示用户确认。
- `parallel: true`（并行检查）只说明 build-and-verify（构建与验证）runner（运行器）支持并行执行，不推断业务依赖。

执行清单：

- 解析每个 check（检查项）的 command（命令），识别第一个可执行入口。
- 对可执行入口执行本机可发现性检查。
- 对包含 pytest-xdist（Pytest 并行插件）参数的 command（命令），检查 `pytest-xdist`（Pytest 并行插件）是否可用。
- 对每个 paths（受影响路径）和 inputs（缓存输入）逐项检查目标路径是否存在；不可访问或缺失按问题报告，不得直接中断初始化。

## Environment Checks（环境检查）

- 确认目标仓库路径存在且是目录。
- 确认 `.build-and-verify`（配置目录）可创建或可写入。
- 覆盖已有配置时，确认备份目录可创建且默认备份路径仍在目标仓库内。
- 发现依赖或环境问题时，必须明确说明用户可以让 agent（代理）协助处理环境和外部依赖问题，但处理前必须获得用户明确授权。

执行清单：

- 目标仓库路径不存在或不是目录时，报告问题、影响和建议。
- `.build-and-verify`（配置目录）已存在时，确认它是目录，并尝试创建再删除临时探针文件来检查可写入性。
- `.build-and-verify`（配置目录）不存在时，确认可创建；检查后不得留下临时目录或探针文件。
- 覆盖已有配置时，确认默认备份路径仍在目标仓库内。
- 备份目录已存在时，确认它是目录，并尝试创建再删除临时探针文件来检查可写入性。
- 备份目录不存在时，确认可创建；检查后不得留下临时目录或探针文件。

报告格式必须包含：

- 问题。
- 影响。
- 建议。
- 是否阻止写入：默认不阻止，除非用户要求停止。

## Local Git Ignore（本地 Git 忽略）

写入 `.build-and-verify/config.json`（配置文件）前必须确保 `.build-and-verify/.gitignore`（忽略规则）存在，并包含：

- `/cache/`
- `/runs/`
- `/backups/`

如果 `.build-and-verify/.gitignore`（忽略规则）已存在，必须保留已有规则，只补齐缺失的默认规则。

## Backup（备份）

覆盖已有 `.build-and-verify/config.json`（配置文件）前必须：

- 复制旧配置到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件）。
- 如果 backups（备份）目录不存在，必须先创建该目录，再复制旧配置。
- 确保 `.build-and-verify/.gitignore`（忽略规则）已经按 Local Git Ignore（本地 Git 忽略）规则包含 `/backups/`。
- 在写入结果中报告备份路径。

## Config Structure Validation（配置结构校验）

写入后必须确认 `.build-and-verify/config.json`（配置文件）符合 runner（运行器）契约：

- 顶层是 object（对象）。
- `build.checks`（构建检查项）和 `verify.checks`（验证检查项）是 list（清单）。
- 每个 check（检查项）有非空且同分组唯一的 `id`（标识）；纯空白字符串必须视为无效。
- 每个 check（检查项）有非空 string（字符串）或 string list（字符串清单）形式的 command（命令）；纯空白字符串必须视为无效。
- `paths`（受影响路径）和 `inputs`（缓存输入）如果存在，必须是 string list（字符串清单），允许为空 string list（字符串清单），但清单项里的纯空白字符串必须视为无效。
- check（检查项）的 `parallel`（并行检查）如果存在，必须是 boolean（布尔值）；`false`（否）等价于不声明 parallel（并行检查）。
- check（检查项）的 `timeoutSeconds`（超时秒数）如果存在，必须是大于 0 的 number（数字），不得是 boolean（布尔值）。
- `verify.maxParallel`（最大并行检查数）如果存在，必须是非负整数。
- `verify.timeoutSeconds`（超时秒数）如果存在，必须是大于 0 的 number（数字）。
