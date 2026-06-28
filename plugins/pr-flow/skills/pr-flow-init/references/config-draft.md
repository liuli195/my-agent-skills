# PR Flow Init Config Draft

agent（代理）展示草案时必须给用户可读摘要，禁止展示完整 YAML（配置格式）草案。只能展示必要字段片段或字段路径，不能用完整配置文件替代用户可读摘要。

## 用户可读摘要

### 本地将写入

| 文件 | 用途 | 是否本次写入 |
| --- | --- | --- |
| `.pr-flow/config.yaml`（配置文件） | PR Flow（拉取请求流程）本地运行配置 | 是 |
| `.pr-flow/pr-template.md`（拉取请求模板） | PR（拉取请求）正文模板 | 是 |
| `.pr-flow/.gitignore`（忽略文件） | 忽略运行态文件 | 是 |

### GitHub 当前状态

只展示 automatic inspection（自动检查）真实读到的状态：

| 项目 | 当前状态 |
| --- | --- |
| GitHub Rulesets（GitHub 规则集） | 已检查值，或 `not inspected`（未检查）/ `no access`（无权限） |
| branch protection（分支保护） | 已检查值，或 `not inspected`（未检查）/ `no access`（无权限） |
| merge methods（合并方式） | 已检查值，或 `not inspected`（未检查）/ `no access`（无权限） |
| auto-delete head branch（自动删除源分支） | 已检查值，或 `not inspected`（未检查）/ `no access`（无权限） |
| PR status checks（拉取请求状态检查） | 已检查值，或 `not inspected`（未检查）/ `no access`（无权限） |

### GitHub 推荐配置

`setup.github`（GitHub 配置建议）只记录人工或后续 agent（代理）可执行的远端待办，不代表 init（初始化）已经写入远端。

远端待办示例：

- 创建或更新 branch ruleset（分支规则集）。
- 启用 `Require a pull request before merging`（合并前要求拉取请求）。
- 设置 `required_approving_review_count: 0`。
- 如需要 PR status checks（拉取请求状态检查），先新增或识别 PR status checks（拉取请求状态检查）的具体 check name（检查名称），再启用 `Require status checks to pass before merging`（合并前要求状态检查通过）。
- 如启用 CodeQL security check（CodeQL 安全检查），在 GitHub Rulesets（GitHub 规则集）中配置 `Require code scanning results`（要求代码扫描结果），选择 `CodeQL` 作为 code scanning tool（代码扫描工具），阈值采用 GitHub 默认阈值，并创建或启用 CodeQL scan producer（CodeQL 扫描结果来源）。
- 如允许 hotfix（热修复）直推，配置 Rulesets bypass（规则集绕过权限）。
- 配置 allowed merge methods（允许合并方式）。

### validation results（校验结果）

草案展示必须预留 validate（校验）摘要区域：

- error（错误）：阻止写入。
- warning（警告）：允许继续，但必须展示风险。
- remote tasks（远端待办）：需要人工或后续 agent（代理）执行的 GitHub（代码托管平台）配置。

## YAML 写入约束

草案 MUST 使用 `defaults`（默认配置）加 `branches`（分支覆盖）。`setup.github`（GitHub 配置建议）MUST NOT be consumed by diagnose、complete、cleanup、hotfix or tweak（诊断、收尾、清理、热修复、小改）。

必须写入或保持的关键字段路径：

- `defaults.baseBranch`
- `defaults.mergeStrategy`
- `defaults.reviewGate.mode`：仅在用户选择保护一个或多个分支时，由 branch protection（分支保护）选择派生为 `github`，不单独提问；选择暂不配置远端保护时保持现有或默认值不变。
- `defaults.hotfix.verifyCommand`
- `defaults.wait`
- `defaults.pr.bodyTemplatePath`
- `defaults.pr.requiredSections`
- `branches.<branch>.remote`
- `branches.<branch>.allowHotfixPush`
- `authorization.phraseHashAlgorithm`：仅当 `allowHotfixPush: true` 时写入或保持。
- `authorization.phraseHash`：仅当 `allowHotfixPush: true` 时写入或保持。
- `setup.github.branchRulesets`
- `setup.github.statusChecks`
- `setup.github.codeScanning`
- `setup.github.allowedMergeMethods`

`authorization must stay top-level`：`authorization`（授权）必须保持在顶层，不能放到 `branches.<branch>`（分支配置）下面。
