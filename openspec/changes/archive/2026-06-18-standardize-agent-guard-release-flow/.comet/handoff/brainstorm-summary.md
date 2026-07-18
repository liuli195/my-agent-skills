# Brainstorm Summary

- Change: standardize-agent-guard-release-flow
- Date: 2026-06-18
- Status: 已确认

## 确认的技术方案

用户确认：发布流程插件化必须并入当前 change，统一设计，后续可分步实现。

确认方案：

- 新增独立 `release-flow` Plugin（发布流程插件），用于在用户所有项目中复用发布流程。
- Agent Guard 是首个适配对象，不再把发布规则硬编码为 Agent Guard 专用脚本。
- `release-flow` 通过项目级配置读取 product id（产品标识）、version sources（版本来源）、tag pattern（标签模板）、latest branch（最新分支）、catalog profiles（市场目录配置）和 allowed latest diff（允许差异白名单）。
- `main` 保持源码、规则、OpenSpec 和发布配置的唯一真相。
- `agent-guard/vX.Y.Z` tag（标签）绑定 Agent Guard 固定版本，GitHub Release（GitHub 发布）绑定同一个 tag。
- `marketplace` 分支保留为 Agent Guard latest channel（最新通道），只为保持现有 Codex/Claude 订阅链接不变并支持自动更新。
- `marketplace` 分支内容由 `release-flow` 从 `main` 生成或校验，不直接开发、不修 bug、不手工维护规则差异。
- 首版实现以最小可用插件为主：config（配置）、dry-run（试运行）、verify（验证），render（生成）按 build 计划确认；不强制引入 GitHub Actions（GitHub 自动化）。

## 关键取舍与风险

- 并入当前 change：统一设计，避免规则与插件形态断层；代价是当前 change 范围明显扩大。
- 使用独立 `release-flow` Plugin：可跨项目复用；代价是需要新增插件包、配置模板和测试面。
- 使用 `marketplace` 分支：保留自动更新能力，但需要防止分支漂移。
- 不使用可移动 tag 模拟 latest：符合 Git/GitHub 语义，但 latest 仍需要分支。
- 首版不做 GitHub Actions：实现更小，验证更直接；代价是发布仍需人工执行插件入口。

## 测试策略

- 单元测试：覆盖 release-flow 配置解析、版本来源读取、tag 模板生成。
- 单元测试：覆盖 tag 版本与 Codex/Claude manifest version（清单版本）一致性。
- 单元测试：覆盖 latest branch（最新分支）差异白名单。
- 插件包测试：覆盖 `plugins/release-flow` 的 Codex/Claude manifest（清单）、Skill（技能）入口、脚本和模板自包含。
- Agent Guard 适配测试：覆盖 fixed tag（固定标签）订阅和 latest branch（最新分支）订阅说明。
- 集成/端到端验证：从用户入口运行 release-flow verify，验证 Agent Guard repo marketplace catalog 和插件包仍可被 installer verify（安装器验证）。

## Spec Patch

- 已新增 `release-flow-plugin` delta spec。
- 已修改 `agent-guard-plugin-runtime` delta spec，明确 Agent Guard 的 fixed release（固定版本发布）和 latest channel（最新通道）由 `release-flow` Plugin 配置和验证。
