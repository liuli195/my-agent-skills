# 云端开发环境

统一入口准备公共依赖并使用本次官方插件运行包，不从旧自有源码克隆或全局 npm 安装获取运行实现。不安装系统运行时，不处理登录凭据，不修改 shell 配置。

## 初始化及更新

先由宿主核对官方对象、发布版本和完整包资源；存在官方文件路径时直接使用。只有资源 URI 时，通过宿主官方能力取得本任务完整相对文件树；脚本不猜缓存路径、不下载账号内容，也不把 URI 当文件路径。

```sh
python scripts/cloud_bootstrap.py init --root <已批准公共依赖目录> --runtime-manifest <本次官方运行来源.json> --project <项目目录>
python scripts/cloud_bootstrap.py update --root <同一目录> --runtime-manifest <重新核验的运行来源.json> --project <项目目录>
```

`--runtime-manifest` 包含 `packages` 对象，键与 `scripts/cloud-environment.json` 的 `runtime_packages[].name` 对应。每项包含：

- `root`：当前完整包绝对路径；不能位于旧 managed/sources、npm 或 skills 中。
- `lifetime`：持久安装为 `installed`，仅本任务资源为 `task`。
- `pluginId`、`releaseId`、`version`、`channel: "RELEASE"`：宿主从官方读取结果核对的身份，不能自行填写假证据。
- `files`：完整包内相对路径到 SHA-256 的映射。脚本校验完整集合、内容、包名、版本和配置要求的技能/启动器；不把本地自述字段当作服务端权限证明。

每次调用重新验证本次输入，不从旧 installed.json 恢复失效路径。所需资源缺失、来源冲突或摘要改变时，在公共依赖安装和项目初始化前失败。输出 `commands` 为当前包的精确 Node 启动参数数组；执行时保持参数边界，不回退 PATH 中的同名全局工具，不改变用户环境。

`--latest` 只允许 `update --latest --only <配置中的公共来源或软件包>`。官方插件内容更新由 plugin-sync 的 Creator 流程负责，初始化不会保存或安装账号插件。公共/第三方 sources、npm 和项目自身 requirements/npm 依赖仍使用原安装工具。

## 发现和旧记录

原生技能发现优先。`--skills-dir` 只导出本次配置明确选择的传统第三方技能，不遍历历史目录重新导出旧自有链接。官方运行包不再建立旧 managed/skills 链接。历史 sources、npm、discovery 记录可保留供恢复和精确清理盘点，不能替代本次运行来源。有效旧安装也不会因仍存在就自动纳入当前导出集合。

已有无效链接、同名冲突及替换需求明确报告，不自动删除。真实发现、脚本运行和恢复验收通过后，按精确清理授权删除旧自有资源；公共依赖、第三方、项目数据和必要正式资产保持。

## 项目接入

projects 配置继续声明 requirements、npm 和 Windows/Linux 准备入口；包运行接入由 `bindings` 声明 `package` 和包内 `script`，不在通用实现按技能短名分支。稳定接入仅使用持久官方安装目录，复用包内 connect/check；现有绑定不同即停止，不隐式覆盖。

任务临时目录不能写成永久项目链接。data-store 已提供 `resolve --runtime <当前技能目录>` 供支持显式实现目录的调用者使用；不支持该输入的项目必须停止。当前 Wow tracked 桥接仍使用稳定目录，只有持久官方目录才能接入；修改项目桥接和真实迁移另按其工作树、基线及授权执行，不能通过改内部变量或临时链接假称完成。数据根与实现目录独立，初始化不迁移业务数据。

## 失败与验证

公共安装中途失败保留真实部分状态并报告，不保证全局回滚；没有完成项目接入不报告 ready。任务资源结束后不可再依赖其路径。开发阶段只在受控夹具验证首次、重复和失败初始化；真实云端安装、客户端发现、项目运行及旧资源清理仍为发布后独立验收。

沿用现有 build-and-verify 默认快速门禁，不新增固定重型冒烟或放宽预算。Windows 既有游戏/编译工具与 Linux 项目依赖准备的职责保持。
