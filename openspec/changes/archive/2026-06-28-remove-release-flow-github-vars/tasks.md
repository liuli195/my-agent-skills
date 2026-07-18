## 1. Contract

- [x] 1.1 更新 release-flow-plugin delta spec，删除非敏感 GitHub Variables 和变量文件要求。
- [x] 1.2 更新 release-flow projection 模板和当前仓库 projection，删除所有非敏感 marketplace identity 变量声明。
- [x] 1.3 更新 release-flow GitHub 配置方案语义，确保 `github-plan` 和 `configure-github --dry-run` 不再输出非敏感 marketplace GitHub Variables。

## 2. Implementation

- [x] 2.1 修改 release_flow.py，让 projection transform 从 identity 引用取值。
- [x] 2.2 删除 `project --vars-file`、`preflight --github-vars-file` 和 `ci-publish --vars-file` 入口。
- [x] 2.3 更新 `validate`、`release-init`、`github-plan`、`configure-github --dry-run`、`project`、`preflight` 和 `ci-publish`，让它们按新 projection identity 模型工作。
- [x] 2.4 更新 workflow 模板和当前仓库 workflow，直接运行 source repo 内脚本，且不写 `release-vars.json`、不传 `--vars-file`。

## 3. Verification

- [x] 3.1 更新 release-flow CLI 测试，覆盖无变量文件的 `project`、`preflight` 和 `ci-publish`。
- [x] 3.2 覆盖旧变量参数被拒绝、projection identity 生成 marketplace、projection 模板和当前 projection 不声明非敏感 GitHub Variables、`github-plan`/`configure-github --dry-run` 不输出非敏感 GitHub Variables。
- [x] 3.3 覆盖 workflow 模板和当前仓库 workflow 不再 checkout 外部插件、不写 `release-vars.json`、不传 `--vars-file`。
- [x] 3.4 运行 release-flow 相关测试和 OpenSpec 严格校验。
