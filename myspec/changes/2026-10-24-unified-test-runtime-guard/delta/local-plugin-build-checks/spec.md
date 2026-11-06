## MODIFIED Requirements

### Requirement: Repository tests enforce runtime boundary

本仓库 MUST 通过既有统一构建与验证总入口，在整个 `tests/` 测试树执行普通测试与显式真实检查之间的运行时边界；真实角色 MUST 按检查标识登记在 `verify.realChecks`（真实检查清单），不得以逐测试函数豁免名单或行为静态扫描代替运行时保护。

#### Scenario: Every repository test has an explicit check role

- **WHEN** 本仓库通过统一入口选择并执行测试检查
- **THEN** 每个测试入口 MUST 唯一归属一个已配置检查，真实检查标识 MUST 唯一且对应实际存在的检查
- **THEN** 未登记检查 MUST 按普通角色执行；真实角色 MUST 明确报告为未享普通无副作用保护，不得自动把未知命令或普通测试登记为真实检查

#### Scenario: Ordinary tests execute real logic without business side effects

- **WHEN** 普通测试在导入、准备、正文、清理、辅助函数、测试夹具或线程中执行
- **THEN** 运行时守卫 MUST 拒绝业务启动外部进程、联网和真实文件变更，包括临时仓库初始化及通过真实进程执行插件命令；业务捕获违规异常或返回成功 MUST NOT 使检查通过
- **THEN** 普通分支与异常规则 MUST 使用真实业务主函数及既有内存或精确执行器接缝，保留必要读取和内存计算，不得把顶层业务结果直接替换为成功

#### Scenario: Focused real groups retain independent core smoke coverage

- **WHEN** 本仓库执行显式登记的真实集成检查
- **THEN** MySpec（自有规格）、构建与验证、拉取请求流程、发布流程、工作区、原生数据和项目环境七组 MUST 各自保留必要公开主路及独立的受影响路径、输入和缓存身份，不得因共享准备合并为一个检查
- **THEN** 必要真实安装、公开命令和对应外部边界 MUST 由聚焦的核心冒烟场景验证；适用的完整成功只读准备 MAY 复用，可变状态 MUST 隔离
- **THEN** 重复异常规则 MUST 保留在既有内存接缝验证；已批准的低收益物理组合 MAY 删除，但 MUST NOT 声称已删除组合仍有逐项真实覆盖

#### Scenario: Entrypoint contracts do not replace runtime enforcement

- **WHEN** 仓库检查核对测试入口、配置角色及依赖归属
- **THEN** 只读静态契约 MUST 覆盖全部测试入口并拒绝遗漏、重复角色及无效选择器，保留各检查实际依赖的路径与输入覆盖
- **THEN** 这些契约 MUST NOT 通过静态调用图或逐函数名单推断副作用安全，也 MUST NOT 代替真实执行中的运行时拒绝与保护证据

#### Scenario: Test migration preserves selection cache and execution limits

- **WHEN** 本仓库执行迁移后的快速、固定基线、拉取请求或完整验证
- **THEN** 七组真实检查 MUST 保留既有独立选择与缓存，普通组 MUST 优先提交但不要求先完成，正式规格校验 MUST 保持独立串行
- **THEN** 已批准的并发、平台条件和60秒总预算 MUST 保持不变，准备成本 MUST 计入同一总预算；完整验证 MUST 执行全部适用配置检查且不读成功缓存跳过
