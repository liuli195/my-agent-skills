# ntfy 公共服务配置流程核对

核对日期：2026-08-17

## 结论

公共 `ntfy.sh` 的匿名通知发布只需要一个随机、难猜、专用的 `topic`（主题），不需要账户、密码、密钥或 `access token`（访问令牌）。当前 iOS（苹果手机系统）应用的实际使用已确认这一匿名路径；账户认证和自建服务器配置不是本插件选项。

## 公共 ntfy.sh 的正确顺序

1. 生成一个随机且难猜的主题。主题无需预先创建；首次订阅或发布时即可使用。主题只能包含字母、数字、下划线和短横线，最长 64 个字符。
2. 在 ntfy 手机应用中添加 `ntfy.sh/<主题>` 订阅。
3. Orca 插件直接向 `https://ntfy.sh/<主题>` 发送匿名 HTTPS POST（安全网页提交）。
4. 先发送一条测试通知，再启用正式状态通知。

官方入门文档说明主题不需要显式创建，并要求使用难猜的名称；发布文档还提供了本地生成随机主题的工具：[Getting started](https://docs.ntfy.sh/#getting-started)、[Picking a topic](https://docs.ntfy.sh/publish/#picking-a-topic)。手机端只需添加主题订阅：[Subscribe from your phone](https://docs.ntfy.sh/subscribe/phone/)。

## 与本方案无关的认证与自建配置

本插件固定向公共 `ntfy.sh` 匿名发布，只使用 `ntfy-topic`。账户认证、`ntfy-token`、密码、密钥文件以及自建服务器的 TLS（传输层安全）、VAPID、FCM（Firebase 云消息）或 APNs（苹果推送服务）配置都不是本插件的配置项，也不会被读取或接受。

## 对当前插件的直接影响

对于已确认的公共随机主题匿名发布，安装配置固定为：先生成随机主题并让用户在手机端订阅，再把主题写入 Orca `secrets`（私密存储）。插件只读取 `ntfy-topic`，即使旧的 `ntfy-token` 仍存在也只忽略、不读取、不删除；插件匿名发布，不发送 `Authorization`（身份验证）请求头。
