# 网页桥接冲突诊断补丁

为 Codex Web GPT（网页桥接工具）增加文字块冲突证据。只增加记录，原有正文匹配、传输、完成判定和报错结果保持不变；不能据此宣称原故障已修复。

## 适用范围

- `codex-chatgpt-web` 6.1.2，Windows x64（64 位系统）。
- 目标：该版本的 `app/browser-helper.cjs`。
- 原文件 SHA-256（文件指纹）：`3d0f23940ce651968a45538fc0afcea2260a8bbafd94f1244515e41085d1a656`。
- 需要 Python（脚本运行工具）3.10 或以上；不安装依赖。
- 文件指纹不同、其他补丁已修改文件、软件名称或版本不匹配时停止，不能强行套用。

`conflict-diagnostic.js` 保存诊断代码，`patch.py` 保存精确替换位置和应用、检查、撤回操作。补丁仅面向上述已核对的打包文件，不是通用版本适配器。

## 增加的信息

在原有冲突原因、字符数和来源位置之外，记录：

- 当前块与已发送块的位置，以及上一个匹配到的旧块位置。
- 按来源位置、节点标识还是相同标签和文字匹配，以及文字、标识是否相同。
- 冲突块前后最多各两个相邻块和最后三个待发送块的类型、匿名指纹、字符数及来源范围。

每条冲突使用随机密钥生成 HMAC（带密钥的内容指纹），不保存密钥。指纹只能在同一条记录内比较，不能跨记录追踪；也不能把三个字符的短句直接枚举出来。没有正文、完整页面、原始节点标识、链接地址或登录信息。

诊断生成失败时保留原错误，并标记 `detailCaptureFailed`（详细记录失败）。记录仍有少量计算及磁盘写入开销，不能承诺零风险。

## 应用与撤回

安装到用户环境需要另行授权。先启动工具，等初始化完成，确认没有运行中的任务，再执行；不要与启动、升级或另一份补丁脚本同时操作。脚本不会启停进程，也不能替用户确认任务空闲。

以下命令在本仓库根目录的 PowerShell（命令窗口）中执行。根据实际安装位置调整目标。

```powershell
$diagnosticTarget = "$env:USERPROFILE\.codex-chatgpt-web\versions\6.1.2-win32-x64\app\browser-helper.cjs"
$diagnosticBackup = "$env:USERPROFILE\.codex-chatgpt-web\diagnostic-backups\6.1.2-browser-helper.original"

python scripts/codex-web-diagnostics/patch.py check --target $diagnosticTarget --backup $diagnosticBackup
python scripts/codex-web-diagnostics/patch.py apply --target $diagnosticTarget --backup $diagnosticBackup
python scripts/codex-web-diagnostics/patch.py check --target $diagnosticTarget --backup $diagnosticBackup

# 撤回；保留备份，以便核对及再次应用。
python scripts/codex-web-diagnostics/patch.py restore --target $diagnosticTarget --backup $diagnosticBackup
```

检查不写文件；应用前保存原件，重复应用不叠加；撤回只接受原文件或本补丁产生的文件。若目标或备份有其他修改，脚本停止，避免覆盖。备份必须在版本目录外。

**启动器会在下次启动时校验版本目录，并恢复官方程序文件。**本补丁不修改校验清单或绕过校验。重新启动后须检查补丁状态，必要时在空闲时重新应用。升级后旧补丁不能直接使用。

补丁只能影响之后从磁盘加载的新浏览器处理进程；已经运行的进程不会自动更新。实际应用后必须通过下一次真实任务的诊断记录确认生效，不能只凭文件已修改认定生效。

## 收集证据

冲突后，原生活动日志仍有冲突原因；原生 `turn-failed`（任务失败）诊断文件额外包含顶层 `markdownConflict`（正文冲突）对象，其中 `detail.schemaVersion=1` 表示本补丁生成了详细记录。

默认诊断目录：`%USERPROFILE%\.codex-chatgpt-web\diagnostics\browser-turns\<本次任务目录>\`。保留该目录及对应的原生活动日志；不要把实际日志提交到仓库。当前工具会轮换清理旧诊断目录，应及时保存到仓库忽略的 `.local/codex-web-diagnostics/` 或其他本地位置。

9 月 27 日现场的磁盘启动器日志没有包含本次错误，活动界面内存日志有记录。代码对日志写入异常不作上报，但这不能证明现场具体是哪一种写入错误。本补丁把新增信息附加到已经能够写出的原生任务诊断文件，不修改启动器日志系统。

## 验证

统一通过仓库 Build and Verify（构建与验证）入口执行：

```powershell
# 可选：明确提供官方文件，仅复制到临时目录测试，不修改安装文件。
$env:CODEX_WEB_DIAGNOSTICS_REFERENCE = $diagnosticTarget
build-and-verify verify --project .
Remove-Item Env:CODEX_WEB_DIAGNOSTICS_REFERENCE
```

检查项 `verify.codex-web-diagnostics` 覆盖应用、重复应用、撤回、不兼容拒绝、备份保护、写入失败、原版与补丁版的判定对照、诊断故障隔离、隐私字段及本地诊断对象传递。提供原文件时，还会从真实脚本入口对官方程序副本应用和撤回，并检查完整程序语法。

临时目录中的验证不等于客户端真实任务验证。安装与真实客户端验证须另行确认；未复现的网页现场原因仍然未知。

上游参考：[6.1.2 发布记录](https://github.com/miuuyy/codex-chatgpt-web/releases/tag/v6.1.2)。
