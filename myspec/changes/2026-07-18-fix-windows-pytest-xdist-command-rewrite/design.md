## Context

当前运行时先用 `shlex.split` 把字符串命令拆成参数，再用 `shlex.join` 拼回命令。该往返操作采用 POSIX 语义；Windows 命令中的 `\.\venv\Scripts\python.exe` 会丢失反斜杠，`set VAR=1&&` 会被错误加引号。参数列表形式不受影响，因此现有测试未覆盖真实失败路径。

## Goals / Non-Goals

**Goals:**

- 为字符串命令注入 `-n <workers>` 时，仅修改 Pytest 命令位置，保留其余原始文本。
- 同时保持参数列表命令、已有 `-n` 参数和依赖检查行为不变。
- 用实际 Windows shell 命令形态建立回归测试。

**Non-Goals:**

- 不引入新的命令执行接口或配置字段。
- 不改变 shell 选择、依赖安装或其他检查的并行策略。
- 不扩展 Pytest 命令识别范围。

## Decisions

- 字符串命令不再经过拆分后重组；根据已识别的 Pytest token 在原字符串对应位置插入 `-n <workers>`。这样修复根因，同时完整保留路径、引号、环境变量设置和 shell 运算符。
- 参数列表命令继续沿用现有列表插入逻辑，避免改变已验证行为。
- 回归测试同时断言转换后的完整命令和传给执行器的命令，覆盖真实调用链。

## Risks / Trade-offs

- [风险] 字符串中存在多个 Pytest token 时只能修改第一个真实命令位置 → 沿用当前“一个检查一条命令”的配置约定，并用既有识别结果限定插入点。
- [风险] Windows 与 POSIX 引号规则不同 → 不重新解释或重新输出原命令，只做局部插入。

## Migration Plan

发布新的 Build and Verify 补丁版本，更新本地插件后由目标仓库执行 `update-runtime`。使用方继续配置 `pytestXdistWorkers`，无需修改命令。

## Open Questions

无。
