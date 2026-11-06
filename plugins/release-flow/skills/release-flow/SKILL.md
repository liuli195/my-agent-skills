---
name: release-flow
description: Use when a project needs a reusable GitHub-based release flow with setup, preflight, publish, CI publish, and verified release account delivery or reconciliation.
---

# Release Flow

Release Flow（发布流程）标准化一个项目的 fixed release（固定版本发布）和 latest channel（最新通道）发布。

Use this skill when the user wants to:

- enable release-flow in a project,
- run release preflight checks with `tag`, `version`, and `bumpPlugins`,
- trigger a GitHub workflow release,
- inspect CI release trace fields from workflow output,
- deliver a verified formal release to the user’s private plugin account, or reconcile a prior successful account response without saving again.

## 运行前提

脚本需要 Python（编程语言）及本技能 `requirements.txt` 声明的 PyYAML（配置解析库）。复用现有环境，确认本次实际解释器；缺库时由原入口报告解释器和声明位置，只报告缺失，由用户决定是否安装。

Git（版本管理工具）、gh（代码托管命令工具）及认证只在相应仓库检查、远端查询或发布功能实际需要时核对；本地模板生成及配置校验不设置统一远端工具门槛。发布流水线中构建软件包所需 Node.js（节点运行时）和 npm（软件包管理器）继续由既有流水线准备，不扩大为全部技能调用的前置条件。

## Boundaries

- Project setup writes only `.release-flow/config.yaml`, `.release-flow/projection.yaml`, and a thin GitHub Workflow entry after explicit authorization.
- `.release-flow/config.yaml` is release-flow generic config; `.release-flow/projection.yaml` owns project marketplace identity, required GitHub Actions Variables, generators, and transforms.
- Codex `.agents/plugins/marketplace.json` is a generated release projection artifact and is not required on the source branch.
- Setup, preflight, and local publish commands do not create release plan files, release records, branches, tags, or release summaries. Account delivery separately preserves the explicit local identity and request evidence needed for safe readback and reconciliation.
- `bumpPlugins` is required; an empty value means catalog/projection-only release.
- Plugin scripts and templates stay inside this plugin package.
- Local publish commands do not create branches, create tags, or push commits.
- GitHub repository settings are modified only after explicit user authorization.
- 禁止在当前对话未获得用户明确确认时修改 GitHub Rulesets（GitHub 规则集）、branch protection（分支保护）、workflow variables（工作流变量）或 repository settings（仓库设置）；未确认时只能输出 remote tasks（远端待办）。

## Commands

Run commands from the target repository root:

```powershell
python <plugin-root>/skills/release-flow/scripts/release_flow.py setup --project .
```

Read `.release-flow/config.yaml` and `.release-flow/projection.yaml` before running release commands.

Use `preflight`（发布前检查） before `publish`（发布）. Trigger publish（发布） only with explicit authorization:

```powershell
python <plugin-root>/skills/release-flow/scripts/release_flow.py publish --project . --tag v0.1.1 --version 0.1.1 --bump-plugins release-flow --authorize-publish
```


## 正式账号交付职责

本技能在原正式发布主路径内负责账号交付及历史对账，插件同步只负责本机检查、安装更新、原双市场及来源隔离。dot（云端助手）固定云端正式对象，本机 Codex（代码代理）和 Claude（代码助手）独立管理；不恢复云端开发对象或跨端联动，不合并两个 NPM（软件包管理器）工具。

1. 先执行原发布前检查和获准的发布，读回既有发布 CI（持续集成）的最终结果、真实 GitHub Release（代码托管发布记录）、标签及发布投影提交。正式发布、完整正式包构建／保留和账号交付分别报告，不能用其中一项成功代替另外两项。
2. 本仓库仅在 `.github/workflows/release.yml`（发布流水线）原 `ci-publish`（持续集成发布）成功后增加两个步骤，通用工作流模板不改：`Build complete dot release packages`（构建完整正式包）从原远端取得精确正式标签并以分离状态检出该市场投影标签，复用目标仓库既有打包入口生成正式完整目录，再封装为 `dot-release-packages.tar`（完整正式包归档）；`Upload complete dot release packages`（保留完整正式包）通过 `actions/upload-artifact`（流水线产物保存动作）只上传该归档文件，产物名称仍为 `dot-release-packages`（完整正式包）。不另上传裸目录、快照清单或插件压缩包。CI（持续集成）不持有个人凭据、不直接写个人账号，不另建发布流水线或强制新任务编号契约。
3. 原 CI（持续集成）全成功后，在个人账号已登录环境取得该归档文件，明确授权交付目录并核对获准精确对象、内容及所选插件 ZIP（压缩包）摘要，再调用本技能同一入口交付。固定命令再次只读真实发布记录及远端标签提交，要求记录不是草稿或预发布、标签提交与快照来源精确一致，再进行账号预检及保存。命令不冒称独立关联某次 CI（持续集成），其成功仍由既有发布主路径先读回。
4. 不要求最新正式版本或当前市场分支尖端。历史正式版本可以从已核实固定标签的干净源码，用既有打包入口重建并封装为相同归档，仍通过同一交付入口使用；不为旧版本新增任务编号要求。当前功能分支、仅有本地标签或干净状态都不能代替真实正式发布证据。

### 完整正式账号包

本仓库复用目标仓库的既有入口，不把打包代码复制到已安装的插件内：

```bash
python <repo>/plugins/tool-lifecycle/pack.py snapshots <output> --project <release-source> --account-mode RELEASE --release-ref <tag>
```

`--release-ref`（正式引用）也接受 `refs/tags/<tag>`（完整标签引用）。打包读取该标签对应的干净正式源码工作树，核对既有标签提交与实际输入一致并记录 `releaseRef`（正式引用）；打包本身不联网、不创建标签、不证明远端发布已成功。无模式离线快照保持原行为，但不能直接交付账号；拒绝新的 DEV（开发）账号模式。

`snapshots.json`（快照清单）记录来源提交及干净状态、输入摘要、版本、完整目录、压缩包摘要、耗时和大小，账号包另有正式模式、真实包名和正式引用。输出目录不在发布输入内；输入未变且完整目录、压缩包及执行位核对通过才复用，依赖变化只重打受影响插件。失败保留上一完整清单和可用产物，损坏或缺失则停止，不提交半包。真实接口的 `pluginPath`（插件路径）使用清单中的完整目录，不是 ZIP（压缩包）路径。

跨环境只运输 `dot-release-packages.tar`（完整正式包归档），其中保留快照清单、ZIP（压缩包）、完整目录及隐藏清单的原布局和模式。外层流水线产物权限归一不会改变归档内部的执行位，不采用单独 ZIP（压缩包）恢复、手工改权限或第二交付路径。

交付命令使用 Python（编程语言）标准库 `tarfile`（归档模块），仅在用户明确授权的 `--delivery-dir`（交付目录）中新建私有临时子目录，受限展开归档。只允许普通文件和目录，拒绝绝对路径、目录穿越、全部链接、异常类型、重复路径及超预算输入，保留原文件模式。内部按快照清单和已校验 ZIP（压缩包）定位完整目录，不信任构建机器的绝对路径；再复用原压缩包摘要、逐文件内容和执行位校验，不修改来源、内容或已批准摘要，不增加依赖。

云端清单保留源码作者和界面字段，缺省值来自已核对仓库及既有发布登记，不伪造联系人或能力，未声明能力标签使用合法空数组并记录来源；按官方[包提交错误契约](https://developers.openai.com/plugins/deploy/submission-errors)离线校验，不冒充平台已接收。依赖按插件现有说明核对，不自动安装外部库、轮子或新隔离环境。

### 交付单个正式私有对象

```bash
python <release-flow-skill>/scripts/release_flow.py deliver-account --project <repo> --manifest <mapping.json> --bundle <dot-release-packages.tar> --delivery-dir <approved-directory> --expected-sha256 <reviewed-plugin-zip-digest> --plugin <selected-key>
```

默认不写账号；检查仍会在已授权交付目录内创建及清理临时解包目录，须先核对这一文件操作授权。用户授权精确内容、私有账号目的地及创建／更新后才加 `--apply`（应用）。`--expected-sha256`（已审阅摘要）是所选插件 ZIP（压缩包）的摘要，不是外层归档摘要。正式模式固定为 RELEASE（正式），本命令不接收来源或直接快照参数，不安装、卸载或切换客户端。新快照须有真实正式引用；新增可选追溯字段缺席不单独使历史正式对象或对账记录失效，不要求为此反复发布或补造历史证据。

- 首次创建需 `plugins.<selected-key>.account.RELEASE`（正式对象映射）空对象；已有对象填写真实 `remotePluginId`（远端标识）及当前版本。缺映射但发现同包名对象则停止，不猜测或盲目新建。正式包保留原名，清单其他内容及本机市场原样保留。
- 已审阅摘要绑定获准内容。核对正式模式、引用、来源、干净状态、输入摘要、仓库来源、包名和版本，逐文件核对目录、压缩包、执行位及摘要，拒绝符号链接。追溯不代替上传内容审阅，禁止夹带凭据。保存前重查同一产物，不临时改名或重打包。
- 只用 `plugin/share/save`（保存私有插件）。创建发送完整目录、`discoverability: PRIVATE`（仅私有）和 `shareTargets: []`（无共享目标）；已有对象更新只发送目录及真实标识，不改分享权限。写入前后通过 `plugin/list`（账号目录）核对真实标识、包名、版本及唯一发现身份。
- 个人对象可返回 `shareContext: null`（无分享上下文），不要求进入工作区分享列表，也不查询该列表。成功响应和精确目录条目可确认请求完成，但权限未独立读回须单列报告。拒绝明确非个人范围、非私有、身份冲突及工作区分享上下文；范围缺失如实记为空。已有对象仅在原保存状态已核对、成功响应及映射为同一标识、原创建参数为私有及空目标、包名及版本匹配时更新，保留原证据。未知创建来源或缺参数继续停止，不猜补或另加网页操作。
- 交付成功或确认没有账号写入的失败会清理本次临时目录；`unknown`（未知）或 `unverified`（未验证）结果保留目录及映射证据，并报告 `retainedDirectory`（保留目录）。不清除未知写入证据，不因清理失败宣称完整成功。
- 应用复用清单锁，写入前原子保存 `saveState`（保存状态）和快照摘要。清单任一条目的未决或未验证记录均阻断新账号写入，不能换插件或来源绕过；只有安全对账准确恢复后才能继续。成功响应实际标识先写回映射，再核对精确目录条目；暂缺只在既有预算内重查，不重发保存、不以目录差异猜标识。
- 超时、断连、响应缺失、终局错误或后检失败保留真实状态及标识，停止后续写入；一次空列表不能清除未决标记，不能安装、删除或回滚未知对象。崩溃遗留锁先核对无运行进程。个人权限未暴露记为不可取得，不冒称执行了不可用的创建服务查询。
- GitHub（代码托管）正式发布已成功，但后续完整包构建或保留失败时，报告“正式发布成功，正式包准备失败”，不得称流水线全成功或继续交付；账号阶段失败则报告“正式发布成功，账号交付未完成”。两者均不能因 dot（云端助手）阶段失败而重发正式发布；账号已发送或结果未知时只按下节安全对账，不盲重发保存。账号 `saved`（已保存）和已核对保存状态也不代表独立权限审核或 dot（云端助手）新会话加载，后者需另有发现及资源运行证据。

### 只读对账

```bash
python <release-flow-skill>/scripts/release_flow.py reconcile-account --project <repo> --manifest <mapping.json> --plugin <selected-key>
```

无需归档或交付目录，不重新解包、打包、发布或保存，默认只读账号及本地记录。`--mode RELEASE|DEV`（正式或开发来源）可选，默认正式；开发仅兼容历史对账，不恢复新的开发交付。用户批准修正精确映射后可加 `--apply`（应用），只原子更新本地保存状态，账号写入始终为零，并复用清单锁。

仅接受原状态为 `unverified`（未验证）、持有成功响应真实标识且与映射一致、包名及版本与原快照一致的记录。响应错误、缺失标识、`pending`（未决）或结果未知继续停止，不靠空列表清除。核对精确账号目录条目、唯一发现身份及暴露权限冲突后才记已对账；权限未暴露仍保留未独立验证，旧创建参数缺失记未记录，不补造证据。历史正式对象、开发对象、映射及未决证据不自动删除，旧记录不因新增追溯字段缺席而反复交付。

账号命令单次预算十分钟、单请求最多两分钟，压缩及展开输入合计超过500 MB（兆字节）按现有限制停止。任何单项预计超过十五分钟或516 MB（兆字节）先请求批准，不拆分规避。
