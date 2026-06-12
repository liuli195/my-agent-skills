# AGENTS.md

## 对话风格

简洁直白，不要过度使用专业词汇。
默认使用简体中文输出。英文技术名词后面跟中文简体释义，例如 `Guard Profile（守卫画像）`、`Runtime（运行时）`。

## 仓库边界

本仓库维护用户级 agent skills 源码。当前范围包含 `agent-guard` 的 Skill（技能）说明、参考文档、Guard Profile（守卫画像）模板、Guard Runtime（守卫运行时）模板、安装/初始化脚本和最小自测。

不要在没有用户明确授权时：

- 安装用户级 Skill。
- 创建或修改目标项目的 hook。
- 启用阻断模式。
- 初始化任何目标项目守卫。
