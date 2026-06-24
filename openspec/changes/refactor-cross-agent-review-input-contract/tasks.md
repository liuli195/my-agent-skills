## 1. 契约与提示词

- [ ] 1.1 更新 `cross-agent-review`（跨代理审查）技能说明，明确核心输入是 `base_ref`（基线引用）+ `head_ref`（头引用）定义的 review subject（审查对象），不是 `diff.patch`（差异补丁）。
- [ ] 1.2 调整 CLI（命令行接口）和 manifest（清单）生成逻辑，用 git commands（命令）记录 diff（差异）、commit list（提交列表）和 changed files（变更文件）。
- [ ] 1.3 将 `reviewer prompt`（审查提示词）模板从 Python 脚本中抽出到独立模板文件，方便修改和复用；Python 脚本仍负责读取和渲染模板。
- [ ] 1.4 调整 `reviewer prompt`（审查提示词）渲染，让输入契约更明确：只给命令、路径、清单、哈希、变更文件摘要和按需读取规则。
- [ ] 1.5 保持插件内部 480 秒单 reviewer（审查代理）超时和 540 秒总 dispatch（派发）超时，并让说明与脚本一致。

## 2. 测试与验证

- [ ] 2.1 增加或调整测试，确认 CLI（命令行接口）不再要求核心 `--diff-file`（差异文件）。
- [ ] 2.2 增加或调整测试，确认 manifest（清单）包含三点 diff（三点差异）、commit list（提交列表）、changed files（变更文件）和 path-scoped diff（按路径限定差异）命令模板，并且不写入 `diff.patch`（差异补丁）。
- [ ] 2.3 增加或调整测试，确认大 `diff`（差异）和大上下文不会进入 reviewer prompt（审查提示词）。
- [ ] 2.4 增加或调整测试，确认 `reviewer prompt`（审查提示词）来自独立模板文件。
- [ ] 2.5 增加或调整测试，确认超时契约由插件内部脚本管理，调用说明不要求外层短超时。
- [ ] 2.6 运行覆盖 `cross-agent-review`（跨代理审查）主流程的回归测试。
