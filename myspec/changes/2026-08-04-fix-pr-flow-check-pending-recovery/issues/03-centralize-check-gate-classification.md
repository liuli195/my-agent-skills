# 03 — 集中检查门禁状态归类

**父问题：** #107

**What to build:** 在 GitHub 检查读取与 PR Flow（拉取请求流程）入口之间建立一个内部检查门禁归类接缝，统一处理命令结果、检查汇总和未知状态；`complete`（收尾）、`tweak`（小改）和 `diagnose`（诊断）复用同一结果。

**Blocked by:** 01 — 统一检查等待与失败恢复; 02 — 有界刷新规则集阻塞并保留真实终态

**Status:** ready-for-human

- [x] 有效必需检查全部通过时，归类为通过并允许现有生命周期继续；不得仅凭非必需检查汇总全部通过放行。
- [x] GitHub CLI 返回退出码 `8` 且输出有效待处理检查时，归类为等待，复用现有有界等待。
- [x] 必需检查查询暂时为空或不可用、但 PR 检查汇总明确显示等待或失败时，分别归类为等待或失败；不得误报为未知通过。
- [x] 检查失败或取消时，三个公开入口统一归类为检查阻塞，并保留检查证据。
- [x] 空结果、格式错误、认证/网络错误或无法确认的新状态归类为显式的检查状态不可用；返回安全停止状态、可复制重试命令，并禁止继续审查或合并。
- [x] 规则集重试路径继续复用归类结果、提交复核和最多一次刷新重试，不新增后台任务、配置或依赖。
- [x] 通过 `complete`、`tweak` 和 `diagnose` 公开入口测试上述行为，并先红后绿。

## Behavior evidence

- Red: 新增 `diagnose` 公开入口回归在基线 `ef0341c2` 上将非必需失败检查误报为阻塞；新增必需检查为空和未知状态探针在实现前分别无法区分等待与检查状态不可用。
- Green: 定向 PR Flow 测试 `python -m pytest -q -p no:cacheprovider tests/test_pr_flow_cli.py tests/test_pr_flow_plugin_package.py tests/test_pr_flow_pi_extension.py`，结果 `285 passed`。
- Green: `build-and-verify verify --project .`，结果 `status: passed`；其中 PR Flow 检查结果为 `285 passed`。
- Green: 审查修复新增查询错误、部分检查数据与未知状态混合矩阵；网络/认证/格式错误不会被汇总等待或失败覆盖；只有明确退出码 8 的等待数据或无错误的有效失败数据才继续分类。
- Green: `complete`、`tweak` 和 `diagnose` 公开入口均覆盖检查状态不可用；`complete` 覆盖必需检查为空时按汇总等待/失败回退和未知状态安全停止，规则集重试路径继续通过同一检查门禁归类。
- Green: 真实 PR #285 用户入口冒烟通过：最终提交 `fc1b6019` 在检查聚合运行期间执行 `complete` 返回 `DISPATCH_REQUIRED / checks_pending`，记录 `no required checks reported` 并从 PR 汇总安全回退，输出可复制 `nextCommand`；此前同一 PR 的等待主路径在检查完成后继续通过检查门禁，随后仅因冒烟用的临时无效审查模式停止，未执行合并。
- Green: 冒烟只临时备份并恢复 `.pr-flow/config.yaml`、`.pr-flow/toolchain.json` 以避免本地工具链记录前置条件阻断；前后哈希一致，未修改远端规则集，PR #285 保持打开。
- Risk: 冒烟使用了临时等待/审查配置和移除工具链记录的安全护栏，因此证明的是检查归类与等待主路径，不等于正式交付配置下的合并授权。
