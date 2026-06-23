---
comet_change: split-fast-full-verification
role: technical-design
canonical_spec: openspec
---

# Test Framework Plugin Design

## 背景

本仓库变更前旧入口 `python scripts/check.py verify` 默认运行完整 pytest（Python 测试框架）套件，本机耗时约 214 秒。A 变更不再只做本仓库专用优化，而是提炼为可复用 `test-framework` Plugin（测试框架插件）：任意仓库可初始化同一套 build（构建检查）、默认 verify（快速验证）和显式 full（全量验证）框架。

## 核心能力

插件只保留三项能力：

- 定义测试产物和目录结构。
- 提供快速缓存测试能力。
- 提供统一配置能力和统一命令入口。

Claude（Claude 版本）和 Codex（Codex 版本）双支持属于同一能力的包装要求，不引入额外业务能力。

## 产物结构

插件本体：

```text
plugins/test-framework/
  .codex-plugin/plugin.json
  .claude-plugin/plugin.json
  skills/test-framework/
    SKILL.md
    scripts/test_framework.py
    scripts/test_framework_runner.py
    assets/templates/
      test-framework/config.json
      test-framework/gitignore
```

目标仓库初始化后：

```text
.test-framework/config.json
.test-framework/.gitignore
.test-framework/cache/
```

首版不生成业务测试、不生成仓库专属映射、不管理 CI（持续集成）。

## 配置模型

目标仓库只维护 `.test-framework/config.json`。配置只声明两组标准检查，并使用 Python（运行器）标准库解析，避免目标仓库额外安装 YAML（配置格式）依赖：

```json
{
  "version": 1,
  "build": {
    "checks": [
      {
        "id": "build.repo",
        "command": "python -c \"print('build ok')\""
      }
    ]
  },
  "verify": {
    "checks": [
      {
        "id": "pytest.main",
        "paths": ["src/**", "tests/**"],
        "command": "python -m pytest",
        "inputs": ["src", "tests"]
      }
    ]
  }
}
```

仓库不定义 `verify.fast.checks`。fast（快速验证）是框架执行模式：在 `verify.checks` 上应用 changed-files（变更文件）筛选和 passed-result cache（通过结果缓存）。

本仓库实际接入时，`.test-framework/config.json` 将 `verify.checks` 拆成 7 个目标仓库检查项：`verify.local-build-contract`、`verify.agent-guard`、`verify.release-flow`、`verify.pr-flow`、`verify.cross-agent-review`、`verify.test-framework` 和 `verify.openspec`。默认 `verify` 根据 changed files（变更文件）只选择受影响检查项；`verify --full` 才运行这 7 个检查项的完整并集。

## 命令模型

目标仓库统一入口由当前安装的 test-framework Skill（测试框架技能）提供。项目级安装时可使用仓库内插件路径；用户级安装时由 agent（代理）使用当前 Skill（技能）目录调用同一个脚本：

```text
python <test-framework-script> build --project <repo>
python <test-framework-script> verify --project <repo>
python <test-framework-script> verify --project <repo> --full
```

语义：

- `build` 运行 configured `build.checks`（配置构建检查项）。
- `verify` 默认从 worktree（工作区）收集 changed files（变更文件），包含 staged tracked changes（已暂存已跟踪变更）、unstaged tracked changes（未暂存已跟踪变更）和 untracked non-ignored files（未跟踪且未忽略文件），选中受影响的 `verify.checks`，再应用 cache（缓存）。
- `verify --full` 运行全部 configured `verify.checks`，不做 changed-files（变更文件）筛选。
- 没有 `paths` 的 verify check（验证检查项）视为 global check（全局检查项）：默认 verify（快速验证）在存在任意 changed file（变更文件）时选择它，干净工作区不选择它。

首版不提供其他命令参数，避免扩大能力边界。

## 缓存策略

缓存目录固定为 `.test-framework/cache/`，由 `.test-framework/.gitignore` 忽略，不纳入 Git（版本管理）。

cache key（缓存键）包含：

- check id（检查项标识）
- command（命令）
- inputs（输入文件或目录内容）
- config（配置）
- Python（运行器）版本
- framework（框架）版本
- cache（缓存）版本

计算 inputs（输入文件或目录内容）时，目录 hash（哈希）必须排除 `.test-framework/cache/`、`.git/` 和 `__pycache__/` 等运行态目录，避免缓存产物反过来改变自己的 cache key（缓存键）。

只缓存 passed（已通过）结果。failed（失败）结果不写入通过缓存。cache miss（缓存未命中）只运行被选中的 check（检查项）本身，不自动升级到 full（全量验证）。没有受影响 check（检查项）时输出 checked（已检查）为空和 full-not-run（全量未运行）证据。

`verify --full` 不读取 cache（缓存）来跳过检查；它运行成功后使用同一 cache key（缓存键）刷新 passed-result cache（通过结果缓存），让后续默认 verify（快速验证）可复用。没有 `inputs` 的 global check（全局检查项）使用当前 changed files（变更文件）作为 cache input（缓存输入）；需要稳定缓存命中的目标仓库应显式配置 `inputs`。有 `paths` 但没有 `inputs` 的 verify check（验证检查项）会扫描目标仓库文件来计算 cache key（缓存键）；大型仓库应显式配置 `inputs` 降低默认 verify（快速验证）开销。

`command` 来自目标仓库配置，按 checked-out repository（已检出仓库）可信输入执行；不要在不信任的仓库内容上运行 build（构建检查）或 verify（验证）。

首版不提供 timeout（超时）配置；可能长时间运行的 `command` 应由目标仓库脚本自行实现超时控制。

## 去耦合边界

插件模板不内置 PR Flow（拉取请求流程）、Release Flow（发布流程）、Comet（双星流程）、Agent Guard（代理守卫）或本仓库业务逻辑。

本仓库接入 test-framework（测试框架）时，通过 `.test-framework/config.json` 声明自己的检查项，例如 plugin manifest（插件清单）、marketplace（市场目录）和 projection（发布投影）。这些映射属于目标仓库配置，不属于插件内置规则。

目标仓库可以把业务检查实现放在仓库自有脚本里，再由 `.test-framework/config.json` 的 `command` 引用；这些脚本不是 test-framework（测试框架）的统一入口。

## 工作流边界

Comet（双星流程）可继续调用：

```text
python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project .
```

PR Flow（拉取请求流程）、Release Flow（发布流程）和 CI（持续集成）不是本 change（变更）的交付内容；它们后续可作为接入方独立迁移到 `verify` 或 `verify --full`。

## 测试策略

测试覆盖四层：

- 插件包装：Claude（Claude 版本）和 Codex（Codex 版本）manifest（清单）、marketplace（市场目录）和 projection（发布投影）。
- 初始化产物：目标仓库生成 `.test-framework/config.json`、`.test-framework/.gitignore` 和 `.test-framework/cache/`。
- 统一入口：`build`、默认 `verify`、`verify --full`。
- 快速缓存：changed-files（变更文件）筛选、cache hit（缓存命中）、cache miss（缓存未命中）、failed（失败）不缓存、no-check（无检查）不回退 full（全量验证）。
- 端到端初始化：在临时仓库运行 `test-framework init` 后实际执行插件入口的 `build`、`verify` 和 `verify --full`。

本 change（变更）只验证框架行为，不解决 full（全量验证）耗时本身；耗时优化由 `optimize-full-verification-runtime` 继续承接。
