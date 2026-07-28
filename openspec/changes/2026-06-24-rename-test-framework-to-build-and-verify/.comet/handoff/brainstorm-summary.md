# Brainstorm Summary

- Change: rename-test-framework-to-build-and-verify
- Date: 2026-06-25

## 确认的约束

- 插件名使用 `build-and-verify`（构建与验证）。
- 本次是 rename（改名），不是删除旧能力再新增新能力。
- 范围保持不变：包含插件、Skill（技能）、脚本、配置目录、仓库引用、OpenSpec（开放规格）和测试引用迁移。
- 根目录 `pyproject.toml`（Python 测试配置）仍在处理范围内。
- 不重构、不重写现有 test-framework（测试框架）实现；只做 rename（改名）和必要引用同步。
- `verify`（验证）默认 fast（快速）。
- `--full`（完整）只允许 PR Flow（拉取请求流程）hotfix（热修复）直推和 PR CI（拉取请求持续集成）。

## 候选技术方案

推荐方案：机械 rename（改名）。移动目录和文件，替换命名、路径、配置目录、错误消息、测试断言和文档引用；保持 runner（运行器）的函数结构和执行逻辑不变。

备选方案：保留兼容 shim（兼容入口）。风险是旧 `test-framework`（测试框架）入口继续存在，与“统一入口”目标冲突。

不采用方案：重写 runner（运行器）或重新设计配置。风险是扩大范围，违反“只改名”约束。

## 关键取舍与风险

- 取舍：不保留旧入口能减少歧义，但会让旧路径立即失效；这是本次 rename（改名）的预期效果。
- 风险：机械替换容易漏掉 marketplace（市场目录）、release projection（发布投影）、Comet（双星流程）、PR Flow（拉取请求流程）和测试引用；需要用测试和搜索校验。
- 风险：删除 `pyproject.toml`（Python 测试配置）后 pytest（Python 测试运行器）默认参数变化；需要把必要参数显式写进 `.build-and-verify/config.json` 的命令。

## 测试策略

- 先更新/运行 build-and-verify（构建与验证）原 test-framework（测试框架）行为测试，确保 rename（改名）后逻辑不变。
- 运行 local build contract（本地构建契约）测试，确保活跃命令不再引用旧入口或根目录测试 wrapper（包装入口）。
- 运行 PR Flow（拉取请求流程）相关测试，确保 hotfix（热修复）保留显式 `--full`（完整），complete/tweak（收尾/小改）不隐式升级。
- 运行 OpenSpec（开放规格）严格校验。

## Spec Patch

无。当前 OpenSpec（开放规格）delta 已按 rename（改名）模型修正并通过严格校验。

## 状态

用户已确认技术方案；下一步创建最终 Design Doc（设计文档）。
