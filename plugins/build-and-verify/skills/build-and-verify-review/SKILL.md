---
name: build-and-verify-review
description: 扫描仓库并审查 Build and Verify（构建与验证）检查项；用户确认后优化配置并运行完整验证
---

# Build and Verify Review（构建与验证审查）

Use this skill when the user asks to review（审查）, audit（审计）, complete（补全）, or optimize（优化） an existing `.build-and-verify/config.json`（配置文件）.

## Hard Boundaries（硬边界）

- 扫描前必须获得用户授权。
- 不得在未确认时运行候选 command（命令），不得安装依赖；必要探测必须遵循 `references/review.md`（审查规则）的成本、副作用和 Git（版本管理）可见改动边界。
- 不修改仓库脚本，不修改测试代码，不写用户级配置，不配置 CI（持续集成）。
- 不自动调整并行数、超时或完整验证预算。
- 用户沉默不能视为确认；最终写入前必须逐项选择并完成整体写入确认。
- 不得直接覆盖 `.build-and-verify/config.json`（配置文件）。
- 完整验证失败时不得自动回滚。

## Shared References（共享参考）

按需读取以下现有规则，不得复制或重新实现：

1. `../build-and-verify-init/references/ecosystem-detection.md`（生态识别规则）：授权后发现已有配置和候选检查项。
2. `references/review.md`（审查规则）：比较候选和已有检查项，生成分组建议。
3. `../build-and-verify-init/references/config-draft.md`（配置草案规则）：合并用户接受的建议。
4. `../build-and-verify-init/references/validation.md`（校验规则）：执行写入前检查、备份写入和结构校验。

## Required Flow（必需流程）

1. 确认目标仓库和扫描授权；读取共享生态识别规则并静态扫描。
2. 读取已有配置和可用性能报告；此步骤不得运行候选 command（命令）。
3. 按 `references/review.md`（审查规则）输出分组结果和修改建议；仅在静态证据不足且用户确认后执行必要候选命令探测。
4. 让用户逐项接受或拒绝建议；High（高）置信度遗漏可默认选中，仍须展示。
5. 使用共享配置草案规则合并已接受建议，再使用共享校验规则执行定向依赖检查和环境检查。
6. 同时展示最终配置差异，以及依赖或环境问题、影响和建议；等待整体写入确认。
7. 用户确认后保存临时 confirmed config（已确认配置），调用 `python <build-and-verify-script> init --project <repo> --config <confirmed-config> --overwrite`（简称 `init --config --overwrite`）。
8. 执行配置结构校验；通过后运行 `python <build-and-verify-script> verify --project <repo> --full`（简称 `verify --full`）。
9. 配置或命令错误产生新的修正草案并重新确认；真实仓库失败保留配置并报告。未经用户明确授权不得从备份恢复。

## Output（输出）

- 审查结果：缺失、错误、重复、缓存和风险。
- 每项证据、置信度、建议和默认选择状态。
- 最终配置差异、依赖检查、环境检查、备份路径、结构校验和完整验证结果。
