## 1. Runtime（运行时）行为

- [x] 1.1 为 `verify.fullBudgetSeconds`（完整验证预算秒数）、`--performance-report`（性能报告）参数、条件报告触发、结果不完整跳过、fast verify（快速验证）隔离和退出状态保持增加进程内回归测试。
- [x] 1.2 在现有命令入口和配置校验中加入可选正整数预算及“报告参数必须配合完整验证”的约束。
- [x] 1.3 复用现有 `CheckResult`（检查结果）实现完整验证总计时、非阻断性能警告、固定报告原子写入及结果完整性保护。

## 2. Plugin（插件）契约与初始化

- [x] 2.1 更新 Build and Verify Skill（构建与验证技能），说明预算是完成后警告、报告触发矩阵、固定报告路径及不改变退出状态的边界。
- [x] 2.2 更新 Build and Verify Init Skill（构建与验证初始化技能）的问卷、配置草案和写后校验规则，使预算保持可选、无仓库专用默认值且写入前必须确认。
- [x] 2.3 更新插件清单和运行时版本元数据，使发布包与复制到目标仓库的运行时保持一致。

## 3. 验证

- [x] 3.1 运行 Build and Verify（构建与验证）聚焦测试，覆盖预算内、超预算、功能失败、显式报告、无预算、固定 schema（结构）、结果不完整、fast verify（快速验证）隔离和报告写入失败。
- [x] 3.2 从发布形态入口初始化临时目标仓库并运行完整验证，确认超预算自动报告且不阻断、未超预算按参数生成报告，并确认测试不依赖本仓库业务检查。
- [x] 3.3 运行 `openspec validate add-build-verify-performance-reporting --strict --no-interactive`（OpenSpec 严格校验）。
- [x] 3.4 运行本仓库 Build and Verify（构建与验证）的 build（构建检查）、fast verify（快速验证）和 full verify（完整验证），且不修改本仓库 `.build-and-verify/config.json`。
