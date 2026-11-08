# 个人云端插件同步

## 唯一入口与官方证据

通过本技能编排，不把工具调用藏入脚本。先取得真实正式发布、标签提交和完整包摘要；工具可用性、个人上下文、权限和客户端能力分别核实。只用官方Creator的create_plugin（创建）或update_plugin（更新）写内容，不用app-server发布，不自建上传/认证客户端。

新建前在个人账号无活动工作区环境中调用list_owned_personal_plugins（个人目录）完整翻页，保留成功原始结果；未知上下文、列表不完整、同名对象或未决操作均停止。create_plugin只有archive参数，不能假造scope参数；上下文改变就重新检查。已有对象从get_plugin_metadata/get_plugin_files（元数据/文件）取得精确ID、USER/PRIVATE及当前release ID，不能按名字猜身份或用缺失字段推定私有。

文件清单完整翻页，需字节时读具体文件，二进制或超限使用官方get_owned_plugin_archive（完整归档）。省略文件会保留：删除只限前次已核实由本产物管理、当前确实存在而新包不再包含的精确路径。未知或生成文件先报告并停止，不删除全部差集，不上传并删除同一路径。保存的完整文件摘要应来自已读取真实字节；服务器合法生成/变换的元数据须明确核验，不以猜测忽略差异。

目标必须是更高的严格正式版本；同版本完整内容一致则跳过，内容不同停止，不让工具自动加补丁或只改build metadata（构建元数据）来伪装升版。更新传archive、原始plugin_id及本次expected_release_id，按计划传delete_paths；并发冲突重新读取和准备，不直接换ID重发旧计划，不修改分享。

## 离线准备与记录

scripts/plugin_sync.py是离线辅助，不联网、不调用Creator或客户端。prepare（准备）受限解包完整正式归档并复用逐文件/模式/摘要核验；证据文件由宿主刚完成的官方读取结果形成，包含release的repository/tagName/tagCommit/publishedAt/isDraft/isPrerelease、完整owned个人列表、current元数据（新建为空）、完整files文件摘要、已核实managedFiles及complete标志。元数据字段须来源明确，不以人工布尔标志替代官方读取事实。

```text
python <skill>/scripts/plugin_sync.py prepare --bundle <正式归档> --delivery-dir <获准目录> --plugin <清单键> --expected-sha256 <审阅ZIP摘要> --evidence <读取证据.json> --output <计划.json>
python <skill>/scripts/plugin_sync.py record --state <本地记录.json> --plan <计划.json>
```

第一条只生成官方工具参数计划，保留临时完整包；第二条在实际发送前核对归档未变化并原子记录pending（待读回），短锁不跨宿主调用。检查全记录无未决/未知/未核验保存后，宿主才对这份计划调用一次指定官方工具；不能把命令执行当成内容保存。

```text
python <skill>/scripts/plugin_sync.py record --state <本地记录.json> --plan <计划.json> --receipt <官方回执.json> --readback <独立读回.json>
```

读回包含明确个人/私有、真实对象及release ID、版本和完整文件摘要及complete；计划、原回执和新读取证据全部保留。短锁及原内容比较保护本地并发，结果未知停止所有再次保存，先用官方读取核对，不清空历史pending或换记录绕过。临时包仅在无使用者且核验完成后精确清理；失败保留位置及原因，不自动删除账号对象。

## 安装、自更新和恢复

Creator不提供客户端安装/卸载工具。Codex使用其已核实官方客户端能力（可用的plugin/install、plugin/uninstall等），Claude使用官方插件命令并记录scope；dot只用其当前实际提供的官方安装能力，缺失时停止，不猜接口或伪装已安装。不得通过内容发布接口代替安装。保持本机双市场与完整来源隔离，按对应原生参考逐项读回。

保存、安装、发现、运行四栏独立记录。已有对象更新失败不重建；未知先查、不盲重试。安装失败按原完整来源恢复，不以重新保存补偿。同步技能自身最后更新，预先保留计划/回执与旧入口，结束旧会话，由新会话确认新指令和来源后续接，不在旧上下文宣称已加载。

当前开发授权只覆盖离线代码和检查。真实账号保存、客户端变更、任务运行迁移及精确清理须按后续明确授权逐项执行，不在开发期勾完。


## 明确拒绝与历史记录收尾

record可用--rejection-evidence处理与成功回执模式互斥的明确未应用证据。此JSON是宿主规范化记录，不是虚构的Creator错误格式：绑定operationId、planSha256、tool、remotePluginId，附完整officialError（isError）、按排序JSON计算的officialErrorSha256、从原文提取的notAppliedQuote、classification=explicit_not_applied及新读取时间readAt/currentReadback。宿主必须确认原文明确说明未应用；普通isError、超时、空列表或版本未变都不够，不能为解锁而填写证明。证据不明确就保留unknown；证据明确仅把该次操作记为rejected，不改对象版本或安装状态。后续重新读取并以新operationId准备，不能重发旧计划。

reconcile-legacy --state <记录> --plugin <精确键> --mode <历史来源键> --success <原成功回执> --readback <新官方完整读取> 默认只核对，--apply仅追加本地resolution，不重写原saveState或历史回执。只有原unverified成功响应真实ID、旧目标版本及产物摘要/完整内容、个人私有和当前release均精确对应才可记verified；不要求补造私人创建参数。pending/unknown且没有明确结果继续停止，不靠同名、对象不存在或更高版本猜成功。历史明确拒绝需完整官方原文证据按同一规则单独核对，不能手动清空状态。全部账号写入仍为零。


## 外部私有适配与官方市场

私有适配包按正式归档中的upstream来源和精确技能集合核对，只经同一Creator流程创建/更新。dot与本机Codex核对同一私有对象ID、版本和六项调用元数据；元数据允许隐式调用不保证模型必然选择。Claude使用官方市场原版，先比较实际官方版本、技能集合和内容；与已批准目标有差异时停止该端安装、迁移和清理，列出差异等待用户决定，不得仅报告后继续。原生技能发现优先；仅在该端官方安装目录已核验可读时读取对应文件回退，不能猜路径、绕过访问拒绝或把私人适配覆盖官方包。


## 明确接受的包装元数据差异

默认仍逐文件比较原始字节摘要。已有 create_plugin 成功回执、完整 USER/PRIVATE 个人目录与文件读回，且用户明确接受具体差异时，可用同一 record 入口离线恢复未核验操作：

```text
python <skill>/scripts/plugin_sync.py record --state <原记录.json> --plan <原计划.json> --receipt <原成功回执.json> --readback <完整读回.json> --accepted-metadata <接受证据.json>
```

接受证据绑定 operationId、planSha256、archiveSha256、plugin_id、release_id、version，并包含 acceptance（accepted=true、非空 reference）、完整 owned（plugins、next_cursor=null）、sourceManifest 和 observedManifest 原始 UTF-8 文本，以及 changes。每项 changes 必须精确记录 JSON Pointer path、action（add 或 replace）和 before/after 的 present 与 value；只允许 /author/name、/author/email、/interface/developerName 中明确接受的非空字符串值，不能删除字段。不得从作者名或邮箱推断账号归属。

两个原始清单文本各自摘要必须对应原计划和官方实际文件摘要；重复 JSON 键、其他字段差异、文件增删或其他文件摘要变化均拒绝。保存证据时保留原始换行，不使用全局换行归一化。此入口不调用账号接口，保留原计划、原回执、来源摘要和实际摘要，标记 verificationMethod=accepted_wrapper_metadata；它不表示所有字节一致，也不证明安装、发现或运行成功。

后续 prepare 的证据可提供 verifiedOperation，复用已核验记录确认同版本无变化。仅同一对象、同一远端 release、相同来源文件和实际文件且原接受证据仍有效时返回 unchanged；未来版本、不同 release 或新增差异不能沿用旧接受范围。版本升高的正常更新仍按完整文件清单与删除清单准备。
