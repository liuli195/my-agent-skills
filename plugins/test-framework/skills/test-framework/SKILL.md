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

## 配置语义

- 目标仓库只定义 `.test-framework/config.json` 的 `build.checks` 和 `verify.checks`。
- 每个 check（检查项）必须有非空且同一分组内唯一的 `id`。
- `verify.checks[].paths` 存在时，默认 verify（快速验证）只选择匹配 changed files（变更文件）的检查项。
- `paths` 支持精确文件、目录前缀（如 `docs/`）、尾部递归前缀（如 `src/**`）和 Python fnmatch（通配匹配）模式。
- 没有 `paths` 的 verify check（验证检查项）是 global check（全局检查项）：默认 verify（快速验证）在存在任意 changed file（变更文件）时选择它，干净工作区不选择它。
- 没有 `inputs` 的 global check（全局检查项）使用当前 changed files（变更文件）计算 cache key（缓存键）；需要更稳定缓存时，目标仓库应显式配置 `inputs`。
- 有 `paths` 但没有 `inputs` 的 verify check（验证检查项）会扫描目标仓库文件来计算 cache key（缓存键）；大型仓库应显式配置 `inputs` 降低默认 verify（快速验证）开销。
- `verify --full`（全量验证）运行全部 `verify.checks`，不读取 cache（缓存）跳过检查；成功通过后会写入或刷新 passed-result cache（通过结果缓存）。
- `command` 来自目标仓库配置，按 checked-out repository（已检出仓库）可信输入执行；不要在不信任的仓库内容上运行 build（构建检查）或 verify（验证）。
- 首版不提供 timeout（超时）配置；可能长时间运行的 `command` 应由目标仓库脚本自行实现超时控制。
