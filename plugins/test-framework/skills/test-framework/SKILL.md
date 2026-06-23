---
name: test-framework
description: 初始化 Test Framework（测试框架）产物，不安装依赖或写入外部配置
---

# Test Framework（测试框架）

Use this skill when a project needs the local Test Framework（测试框架）artifact layout initialized.

## 边界

- 只初始化测试框架配置产物。
- 不安装依赖。
- 不写用户级配置。
- 不配置 CI（持续集成）。
- 不内置仓库业务逻辑。
- 不向目标仓库复制 runner（运行器）；build（构建检查）和 verify（验证）直接调用本插件脚本。

## 命令示例

```bash
python scripts/test_framework.py init --project .
python scripts/test_framework.py build --project .
python scripts/test_framework.py verify --project .
python scripts/test_framework.py verify --project . --full
```

项目级安装时，可从仓库内插件路径调用：

```bash
python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project .
```

用户级安装时，由 agent（代理）使用当前 Skill（技能）所在目录调用同一个 `scripts/test_framework.py`。
