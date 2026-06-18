## 1. 规格与设计

- [x] 1.1 更新 `openspec/changes/standardize-agent-guard-release-flow/proposal.md`，明确本次产物是双端兼容 `release-flow` Plugin。
- [x] 1.2 更新 `openspec/changes/standardize-agent-guard-release-flow/design.md`，固化 GitHub Workflow、Rulesets、Actions Variables 和发布投影模型。
- [x] 1.3 更新 `openspec/changes/standardize-agent-guard-release-flow/specs/release-flow-plugin/spec.md`，定义插件结构、配置、变量注册表、发布阶段和验证契约。
- [x] 1.4 更新 `openspec/changes/standardize-agent-guard-release-flow/specs/agent-guard-plugin-runtime/spec.md`，明确 Agent Guard 通过 release-flow 管理 fixed release 和 latest channel。
- [x] 1.5 更新 Superpowers Design Doc，替换旧的 catalog profile / allowed diff 白名单方案。
- [x] 1.6 将旧 implementation plan 标记为作废，避免按旧方案实现。

## 2. Release Flow Plugin 结构

- [x] 2.1 新增 `plugins/release-flow/.codex-plugin/plugin.json`，遵循 Codex 官方插件 manifest 结构。
- [x] 2.2 新增 `plugins/release-flow/.claude-plugin/plugin.json`，遵循 Claude 官方插件 manifest 结构。
- [x] 2.3 新增 `plugins/release-flow/skills/release-flow/SKILL.md`，作为 Codex/Claude 共享技能入口。
- [x] 2.4 新增 `plugins/release-flow/skills/release-flow/scripts/`，承载确定性脚本。
- [x] 2.5 新增 `plugins/release-flow/skills/release-flow/assets/templates/`，承载 `.release-flow` 和 GitHub Workflow 模板。

## 3. 项目发布配置

- [x] 3.1 新增 `.release-flow/config.yaml` 模板，保存发布流程配置。
- [x] 3.2 新增 `.release-flow/projection.yaml` 模板，保存发布投影变量注册表。
- [x] 3.3 新增 `.release-flow/.gitignore` 模板，只忽略 `/releases/`。
- [x] 3.4 明确 `.release-flow/releases/<tag>/` 为本地发布记录，不进 Git。
- [x] 3.5 禁止在 `projection.yaml` 保存变量值或 secret，只允许保存变量名、说明、示例和注入规则。

## 4. 初始化与 GitHub 配置

- [x] 4.1 实现项目启用检查，调研仓库并生成 `.release-flow` 配置和薄 workflow；脚本和模板保留在插件包中。
- [x] 4.2 实现 GitHub 仓库配置方案输出，覆盖 Actions 权限、Rulesets 和 Actions Variables。
- [x] 4.3 首版 `configure-github --authorize-github` 不实际写 GitHub，返回授权边界状态。
- [x] 4.4 用户未授权时，输出可手动执行的配置步骤。

## 5. 发布流程

- [x] 5.1 实现首版 preflight，检查本地配置、变量快照、tag/version、manifest 和发布投影；GitHub Rulesets/workflow 权限由 `github-plan` 和 `configure-github --dry-run` 输出手动步骤，不做远端回读。
- [x] 5.2 实现单次发布初始化，写入 `.release-flow/releases/<tag>/release-plan.json`。
- [x] 5.3 实现 publish，读取已存在 release-plan，使用 `workflow_dispatch` 触发 GitHub Workflow，本地不创建发布分支、不打 tag、不 push。
- [x] 5.4 实现 GitHub Workflow 模板：checkout sourceRef、安装 release-flow 依赖、读取 projection、注入 GitHub Variables、创建或更新 `marketplace`、创建 tag 和 GitHub Release。
- [x] 5.5 实现 summarize，写入 workflow run 信息和发布总结。

## 6. Agent Guard 适配与验证

- [x] 6.1 为当前仓库生成 Agent Guard 的 `.release-flow/config.yaml`。
- [x] 6.2 为当前仓库生成 Agent Guard 的 `.release-flow/projection.yaml`，覆盖 Codex/Claude marketplace catalog 发布态变量。
- [x] 6.3 增加测试，检查 `release-flow` 插件同时包含 Codex manifest、Claude manifest、Skill、脚本和模板。
- [x] 6.4 增加测试，检查 projection 能解释 `main` 与 `marketplace` 的合法发布差异。
- [x] 6.5 运行 OpenSpec strict validation（严格校验）和覆盖发布主流程的端到端回归。
