# 02 — 每次验证复用一个 MySpec 候选包

**What to build（构建内容）：** 当贡献者运行一次非缓存 `verify.my-spec`（MySpec 验证）时，本地验证只生成一次当前检出的候选 Tarball（压缩包），并行工作进程共享该只读包，同时每个测试继续使用独立安装和运行状态；CI（持续集成）已提供候选包时不重复生成。

**Blocked by（前置票据）：** 01 — 保护隔离 MySpec 发布形态验证。

**Status（状态）：** ready-for-agent

- [x] 本地测试控制进程在并行工作进程启动前通过官方打包 Interface（接口）准备候选包。
- [x] 一次非缓存 `verify.my-spec` 只生成一次当前候选包，所有并行工作进程消费同一只读包。
- [x] 每个测试的安装前缀、用户目录、MySpec 运行状态和日志保持隔离。
- [x] 模拟其他版本、升级或故障场景的包继续独立生成，不被错误复用。
- [x] CI 明确提供当前候选包时验证并复用该文件，不再次打包。
- [x] Build and Verify（构建与验证）能够感知候选包准备逻辑的变化并运行 `verify.my-spec`。
- [x] 单次非缓存 `verify.my-spec`（MySpec 验证）稳定压缩到约 30 秒，并记录三次耗时、打包次数、`checked`（已检查）和最终状态。
- [x] 票据 01 的完整隔离发布形态验证继续通过。

## Behavior Evidence（行为证据）

- Red（红灯）：首次实现只在单一测试中顺序安装两次并比较复制包字节，重复打包也可能得到相同字节，不能证明一次官方打包或工作进程继承。
- Green（绿灯）：控制进程一次打包、外部候选零打包、目录调用、独立安装、外部临时目录中的轻量 4 worker 路径继承和 Build and Verify（构建与验证）变化感知均已通过；其他版本包继续走独立打包路径。
- Review（审查）：真实 4 worker 共享路径阻断、无关的 8 次重复安装及源码工作树临时文件污染均已修复。
- Integration（集成）：固定基线 `309243c` 快速验证报告 `checked` 非空并包含 `verify.my-spec`，`full-not-run: true`、`status: passed`。
- Performance（性能）：同机、同命令、无外部候选包各运行三次。基线墙钟为 239/242/262 秒，中位数 242 秒；变更后为 239/250/253 秒，中位数 250 秒。Pytest（测试框架）内部中位数由 240.95 秒降至 238.10 秒，仅下降约 1.2%，未达到 30%。基线每次隔离安装缺少候选时重复打包；变更后检查证明控制进程打包 1 次且 4 worker 共享。
- Decision（决定）：一次打包复用未达到性能目标后，用户确认继续采用规格中的条件方案：每个 worker 建立只读安装模板，再复制到测试级独立前缀；不得共享可写运行状态。
- Review（审查）：模板复制保留 Linux npm 符号链接；正常、异常和 worker 会话结束清理均有证据；单进程计数与 4 个真实 worker 测试共同证明每 worker 一次安装、独立复制前缀和裸 CLI 可运行，无剩余阻断。
- Performance after worker template（工作进程模板后性能）：墙钟为 214/209/234 秒，中位数 214 秒，相对基线 242 秒下降约 11.6%；Pytest（测试框架）内部中位数为 211.99 秒，相对基线 240.95 秒下降约 12.0%，仍未达到 30%。
- Revised target（修订目标）：用户要求单个 `verify.my-spec` 检查稳定压缩到约 30 秒，并授权在达标前持续实施，无需逐轮询问；允许删除不再提供独立行为证据的测试逻辑，并把除票据 01 完整发布形态路径之外的测试改为进程内模拟。
- Latest Red（最新红灯）：第二轮进程内改造仍耗时 198.64 秒；`test_packed_myspec_dev_doctor_identity_ignores_unrelated_files_and_tracks_closure` 与 `test_packed_myspec_doctor_uses_actual_installation_not_mode_state` 失败。普通进程内测试必须不执行 npm 安装或前缀复制；进程内加载必须基于传入裸 CLI 对应的已安装 `spec_ops.py`，不能固定加载仓库根实现。源码身份/实现变化场景与票据 01 的两条完整真实路径继续走真实 CLI。
- Optimization batch（优化批次）：把真实 npm 安装压缩到票据 01 必需的最少路径。放弃为普通测试复制完整 npm 前缀：对非真实 CLI 测试，直接在测试自己的临时前缀构造轻量包树（复制仓库 MySpec 包内容并嵌入共享 management 实现、创建仅供路径推导的启动文件），通过该测试本地 `spec_ops.py` 进程内运行；这样既不共享可变模板，也不执行 npm 安装/前缀复制。必须真实执行的票据 01 路径直接从候选 Tarball 做独立 npm 安装，不再复制 worker 模板。删除不再需要的安装模板实现及探针，只保留一次候选打包、4 worker 候选继承、真实裸 CLI 与完整业务流程证据。
- Latest benchmark red（最新基准红灯）：共享轻量包树与少量私有副本已让测试通过，但 `--durations=40` 显示 `verify.my-spec` 仍约 214 秒；最大单项为 update 恢复 98 秒、源码身份 59 秒、update/模式切换 20–44 秒。剩余瓶颈是 fake client/git/npm 的真实子进程和重复 E2E（端到端）分支，不是包树复制。
- Runtime budget（耗时预算）：保留票据 01 的真实 Tarball 裸 CLI 与完整工作流，二者合计约 20 秒；除此之外，标准检查中的测试不得再通过 fake client 子进程证明普通逻辑分支。删除重复 E2E 逻辑，或直接调用已加载的 management/spec_ops 进程内 Interface（接口）并模拟 `_run`/Git/npm/client 结果。优先处理所有超过 3 秒的测试，源码身份族只保留一条必要真实路径，update/mode-switch/doctor 分支不得保留十余条真实子进程组合。每轮使用 `--durations` 验证，直到整个检查约 30 秒。
- Latest durations（最新耗时）：进程内 fake command runner 已将检查降至约 96–105 秒。剩余最大项是源码身份完整 E2E 约 51 秒和实现差异重新确认 E2E 约 21 秒；删除这两条重复 E2E：前者由较窄的 published-ancestor/closure 证据覆盖，后者由 `test_myspec_final_apply_rejects_unconfirmed_implementation_identity` 与未变化复用确认场景覆盖。同步删除对应 E2E allowlist（端到端白名单）和真实 CLI 名单项，再按耗时继续收窄。
- Final performance（最终性能）：最终代码连续三次非缓存执行检查命令分别为 33.46、33.11、33.70 秒，中位数 33.46 秒；固定基线 Build and Verify（构建与验证）报告 `duration: verify.my-spec seconds=35.83`、`checked` 非空且包含 `verify.my-spec`、`full-not-run: true`、`status: passed`。相对基线中位数 242 秒下降约 86.2%。
- Final coverage（最终覆盖）：保留官方候选包一次打包、4 worker 继承、隔离裸 `myspec`、完整预览/差异/正式应用及真实安装资源检查；普通逻辑分支改为进程内模拟，并删除两条已有更窄接缝覆盖的重复 E2E（端到端）场景。
- Overall review（整体审查）：fake Git/npm 未声明命令现返回非零；实现差异重新确认及实现闭包/远端删除均恢复窄覆盖；共享轻量包具备完整内容指纹守卫；外部候选环境、全局 `subprocess.run` 异常路径均恢复；4 worker 证明候选共享及 HOME、日志、状态和前缀隔离。Standards（规范）与 Spec（规格）定向复审均无阻断。
- Unresolved risks（未解决风险）：进程内模块缓存和全局 `subprocess.run` 替换仅用于每个串行 worker 内的测试模拟，并由异常恢复检查保护；作为非阻断风险保留。固定基线、最终三次非缓存性能验证及定向复审均已完成，无剩余阻断。
