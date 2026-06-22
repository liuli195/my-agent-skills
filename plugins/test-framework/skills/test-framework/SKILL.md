---
name: test-framework
description: 初始化 Test Framework（测试框架）产物，不安装依赖或写入外部配置
---

# Test Framework（测试框架）

Use this skill when a project needs the local Test Framework（测试框架）artifact layout initialized.

## 边界

- 只初始化测试框架产物。
- 不安装依赖。
- 不写用户级配置。
- 不配置 CI（持续集成）。
- 不内置仓库业务逻辑。

## 命令示例

```bash
python test_framework.py init
```
