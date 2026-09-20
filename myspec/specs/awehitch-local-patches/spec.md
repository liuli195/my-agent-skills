# awehitch-local-patches Specification

## Purpose

让第三方包 awehitch 升级后先接受真实入口验证，只重放仍有失败证据且收益合理的本地修复；避免旧补丁凭静态猜测污染新版本。

## Requirements

### Requirement: 先升级实测，再准入补丁

系统 MUST 先安装未打本地补丁的目标版本并逐项运行真实行为测试。只有在该干净版本上稳定复现原始症状的补丁，才可加入 `scripts/awehitch-local-patches.ps1`。版本发布说明、源码相似或静态特征 MUST NOT 单独作为保留补丁的依据。

#### Scenario: 新版本发布

- **WHEN** 开发者准备升级 awehitch
- **THEN** 开发者 MUST 先备份当前安装、配置和状态
- **THEN** 开发者 MUST 安装干净新版本并完成逐项实测
- **THEN** 开发者 MUST NOT 在首轮实测前运行或修改旧补丁脚本

#### Scenario: 旧问题未复现

- **WHEN** 干净新版本的真实入口不能复现某个旧问题
- **THEN** 该补丁 MUST NOT 在新版本上重放

### Requirement: 补丁脚本只支持已验证版本和已准入项目

脚本 MUST 明确限制到已经验证的 awehitch 版本，MUST 列出本版本实际准入的补丁，MUST 逐项报告结论，且 MUST 幂等。文件缺失或锚点不能唯一命中时，脚本 MUST 不修改该项并以非零退出码结束。

#### Scenario: 版本不匹配

- **WHEN** 当前安装版本不是脚本声明的已验证版本
- **THEN** 脚本 MUST 拒绝修改安装包

#### Scenario: 重复运行

- **WHEN** 所有准入补丁均已存在时再次运行脚本
- **THEN** 脚本 MUST NOT 重写已处理的第三方包文件

### Requirement: 补丁前保留原件

系统 MUST 在首次改动每个第三方包文件前创建同目录 `.orig` 备份，已有备份 MUST NOT 被覆盖。

#### Scenario: 重复重放

- **WHEN** 同一补丁被多次检查或重放
- **THEN** 首次创建的 `.orig` 原件 MUST 保持不变

### Requirement: 0.3.2 的准入补丁

awehitch 0.3.2 只准入以下四项：固定浏览器缩放、剔除长消息折叠标签、保持 Codex（代码代理）项目级注册、使发送文本满足 `[C2C]` 和 1024 字节限制。旧补丁 2、5、6 MUST NOT 重放，除非未来重新取得对应版本的真实失败证据。

#### Scenario: 发送折叠长消息

- **WHEN** 发送一条小于 1024 字节且页面会折叠的控制消息
- **THEN** 读回比对 MUST 忽略末尾的展开或收起标签并报告发送成功

#### Scenario: 运行接入命令

- **WHEN** 开发者执行 `awehitch up`
- **THEN** Codex（代码代理）用户级配置 MUST 逐字节不变
- **THEN** 已有项目级配置的工作区 MUST 仍被诊断为已接入

#### Scenario: 渲染发送文本

- **WHEN** 按允许的最长连接器名渲染现有 Codex（代码代理）技能
- **THEN** 每个需要发送的控制文本块 MUST 以 `[C2C]` 开头且不超过 1024 字节

### Requirement: 只更新已验证客户端

模板补丁应用成功后，脚本 MUST 只重渲染本次验证范围内且已经存在的 Codex（代码代理）技能，MUST NOT 创建或改写未参与验证的其他客户端安装。

#### Scenario: 其他客户端未参与验证

- **WHEN** 模板补丁应用成功但其他客户端不在本轮验证范围内
- **THEN** 脚本 MUST NOT 创建或改写该客户端的技能文件
