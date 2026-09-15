## Context

`build-and-verify`（构建与验证）当前 runtime（运行时）随 Plugin（插件）安装在用户级缓存目录。这个路径不适合作为仓库文档和 CI（持续集成）的固定命令入口。

现有实现已经是轻量 Python（Python 语言）脚本：`build_and_verify.py` 负责命令入口，`build_and_verify_runner.py` 负责读取 `.build-and-verify/config.json` 并运行检查。本次变更复用这套结构，只把 runtime（运行时）复制到仓库内固定位置。

## Goals / Non-Goals

**Goals:**

- 仓库内提供固定 runtime（运行时）入口，供文档和 CI（持续集成）使用。
- 用户级和仓库内 runtime（运行时）保持同一份能力。
- `update-runtime`（更新运行时）显式同步 runtime（运行时）。
- `build`（构建）和 `verify`（验证）只提示版本落后，不自动改仓库文件。
- Skill（技能）文案、spec（规格）、测试和 CI（持续集成）入口同步更新。

**Non-Goals:**

- 不实现项目级 Plugin（插件）安装器。
- 不引入新依赖。
- 不自动修改用户级 Codex（代码助手）配置。
- 不在 `verify/build`（验证/构建）中自动更新仓库文件。

## Decisions

1. Runtime（运行时）复制到 `.build-and-verify/runtime/`。

   这让 CI（持续集成）和文档使用稳定路径，不依赖用户级 Plugin（插件）缓存。替代方案是复制整个 Plugin（插件）到 `plugins/`，但本次只需要验证入口，复制完整 Plugin（插件）会扩大范围。

2. `init`（初始化）和 `update-runtime`（更新运行时）使用同一套复制逻辑。

   `init`（初始化）负责首次创建配置和 runtime（运行时）快照；`update-runtime`（更新运行时）只刷新 runtime（运行时）快照。复制来源固定为“当前正在执行的 runtime（运行时）目录”。如果仓库内旧 runtime（运行时）发现用户级新版，提示必须给出用户级新版脚本路径，让用户用新版脚本执行 `update-runtime`（更新运行时）。

3. `build_and_verify.py` 保持同一份命令能力。

   用户级和仓库内入口都支持 `init`、`update-runtime`、`build` 和 `verify`。差异只来自当前文件所在位置，不来自分叉代码。

4. 版本检查只提示，不更新。

   `build`（构建）和 `verify`（验证）启动时尽力查找可发现的用户级 runtime（运行时）版本。仓库版本落后时输出提示和可执行的新版脚本命令；查不到用户级 runtime（运行时）时静默继续。发现范围覆盖 Codex（代码助手）和 Claude（Claude 版本）常见用户级位置，找不到不影响 CI（持续集成）。自动更新会让验证命令产生副作用，因此不采用。

## Risks / Trade-offs

- 用户级 runtime（运行时）不可发现 -> 静默继续，CI（持续集成）不受影响。
- 用户忘记运行 `update-runtime`（更新运行时） -> `build/verify`（构建/验证）提示落后版本。
- runtime（运行时）快照进入 Git（版本管理） -> 增加少量仓库文件，但换来稳定命令入口。
- 验证覆盖不足 -> 必须从用户入口跑端到端回归，证明复制后的仓库 runtime（运行时）能实际执行 `update-runtime`、`build` 和 `verify`（更新运行时/构建/验证）。
