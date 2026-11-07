# PR Flow Windows 命令行垫片解析修复

## Problem Statement

Windows 上，PR Flow（拉取请求流程）的 hotfix（热修复）验证命令可能依赖 npm CLI（命令行程序）生成的 `.cmd` 或 `.bat` 命令行垫片。当前执行路径使用 `shell=False`（不启用命令 shell）直接启动配置命令的第一个参数，无法将 PATH（环境变量路径）中的垫片解析为可启动的绝对路径，导致默认的 `build-and-verify verify --project . --full` 在验证阶段失败，并阻止合法的 hotfix 继续执行。

## Solution

让 Windows 的 hotfix 验证执行路径在启动前解析配置命令的第一个参数；解析成功时使用解析后的路径，解析失败时保留原参数并沿用现有错误处理。继续使用参数列表和 `shell=False`，使 npm CLI 垫片可运行且不扩大 shell 命令解释范围。

## User Stories

1. 作为 Windows 仓库维护者，我希望使用默认的 hotfix 验证命令，以便无需把本机用户目录的绝对路径写入仓库配置。
2. 作为 Windows 仓库维护者，我希望 PATH 中的 `.cmd` 或 `.bat` 验证命令能够被启动，以便 hotfix 验证可以到达后续授权和推送前检查。
3. 作为 Linux 或 macOS 仓库维护者，我希望现有验证命令解析和执行行为保持不变，以便本次修复不会改变其他平台的 PR Flow 行为。
4. 作为仓库维护者，我希望找不到验证命令时仍得到明确的 `hotfix_verify_failed` 停止状态，以便错误能够安全关闭而不是继续推送。
5. 作为项目维护者，我希望该修复只影响 hotfix 验证命令的启动，不改变授权、远端复核、推送和审计顺序。

## Implementation Decisions

- 修改现有 hotfix 验证命令执行模块，不增加新模块、依赖或配置字段。
- 仅解析命令参数列表的第一个元素；其余参数保持原样。
- Windows 使用已有的可执行文件路径解析能力解析 PATH 中的 `.cmd`、`.bat` 和其他可执行文件。
- 解析成功后使用绝对路径；解析失败后保留原命令，让现有 `FileNotFoundError` 到 `hotfix_verify_failed` 的转换继续生效。
- 保持 `shell=False` 和当前跨平台命令参数解析方式。
- 默认配置和现有仓库配置不变；修复在运行时覆盖所有使用该执行路径的验证命令。

## Testing Decisions

- 最高复用测试接缝是现有 hotfix 验证命令执行接口；它直接观察配置命令是否以正确的可执行路径、参数和 shell 模式启动。
- 增加 Windows 命令行垫片解析回归测试，验证 `.cmd` 路径被解析后传给进程启动器。
- 增加找不到命令的回归测试，验证原命令保留、错误原因仍为 `hotfix_verify_failed`、返回码仍为 `127`。
- 保留并运行现有非 Windows 参数解析测试，证明 Linux/macOS 行为未改变。
- 实施完成后通过真实的 PR Flow hotfix 验证入口进行最小 Windows 命令行垫片冒烟，并运行仓库 Build and Verify（构建与验证）快速检查。

## Out of Scope

- 不把默认命令改成平台相关的 `.cmd` 路径。
- 不启用 `shell=True`，不引入 shell 注入或新的命令解释语义。
- 不修改 `complete`、`tweak`、`cleanup`、`diagnose`、PR CI（持续集成）或 Build and Verify 本身。
- 不修改授权短语、远端目标复核、推送、审计和工作树清理逻辑。
- 不安装依赖、刷新客户端、发布插件或执行 Release Flow（发布流程）。

## Further Notes

该变更修复 GitHub Issue（问题单）#269。它是运行时缺陷，因此采用标准流程的最小单票据路径，而不是仅适用于非缺陷小改动的 `pr-flow-tweak`。
