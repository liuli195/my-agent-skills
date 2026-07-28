# Brainstorm Summary

- Change: refactor-cross-agent-review-input-contract
- Date: 2026-06-24

## 确认的技术方案

采用方案 A：用 review subject（审查对象）作为 `cross-agent-review`（跨代理审查）的核心契约。调用方仍通过 Python（脚本）运行插件，但核心输入从 `diff.patch`（差异补丁）改为 `base_ref`（基线引用）和 `head_ref`（头引用）。Python（脚本）生成 `manifest.json`（清单），记录三点 diff（三点差异）命令、commit list（提交列表）命令、changed files（变更文件）命令和 path-scoped diff（按路径限定差异）命令模板。

系统不保存、不生成、不传递 `diff.patch`（差异补丁）。Reviewer（审查者）需要查看差异时，按 `manifest.json`（清单）中的命令模板执行路径范围读取。

`reviewer prompt`（审查提示词）模板从 Python（脚本）中抽到独立模板文件，目的是方便修改和复用。Python（脚本）仍负责读取模板、填充变量、写入 `prompts/<role>.txt`，并派发 reviewer（审查者）。

## 关键取舍与风险

- 移除 `diff.patch`（差异补丁）会要求所有审查范围都通过 git commands（命令）复现；这更稳定，但需要测试覆盖 rename（重命名）、delete（删除）和 path with spaces（带空格路径）。
- 独立模板让提示词更容易维护，但模板渲染只做简单占位符替换，不引入新依赖。
- 插件内部继续管理 480 秒 reviewer timeout（审查者超时）和 540 秒 dispatch timeout（派发超时）；调用说明禁止外层短 timeout（超时）包装。

## 测试策略

- 先写失败测试，确认 CLI（命令行接口）不再要求 `--diff-file`（差异文件）。
- 验证输出目录没有 `inputs/diff.patch`（差异补丁）。
- 验证 `manifest.json`（清单）包含三点 diff（三点差异）、commit list（提交列表）、changed files（变更文件）和 path-scoped diff（按路径限定差异）命令模板。
- 验证 `reviewer prompt`（审查提示词）来自独立模板，且不内联 diff output（差异输出）或上下文文件正文。
- 验证 480 秒和 540 秒内部 timeout（超时）契约保持不变，技能说明禁止外层短 timeout（超时）。

## Spec Patch

无。当前 OpenSpec delta spec（增量规格）已经覆盖确认后的方案。
