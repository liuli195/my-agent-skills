# 验证记录

## 已验证

- TDD（测试驱动开发）红灯证明旧实现会额外读取 `ntfy-token`，版本仍为 `1.0.0`；最小实现后相同检查转绿。
- `node --test tests/orca_ntfy.test.mjs`：`13/13` 通过，覆盖匿名请求、仅读取主题、无授权请求头、状态映射、去重、重试、缺少主题和敏感信息保护。
- `build-and-verify verify --project <当前工作树> --base 19db30728efb0cf1eacca914abd80f7870ffbdbc`：`status: passed`，`checked` 包含 `verify.local-build-contract` 和 `verify.runtime-boundaries`；首次实际运行通过 `83` 个 Python（运行环境）测试和 `17` 个 Node.js（运行环境）测试，最终复跑命中有效缓存。
- 真实公共服务冒烟：通过实际 `activate(orca)` 插件入口向运行时随机且未输出的 `ntfy.sh` 主题发送 `blocked`（阻塞）通知，HTTP（网页传输协议）状态为 `200`，只读取 `ntfy-topic`，请求没有 `Authorization`（授权）头，退出码为 `0`。
- Standards（标准）与 Spec（规格）两轴 Reviewer（审查者）复核均无剩余阻塞发现。
- `myspec validate-main myspec/specs`：正式规格应用后校验通过。

## 未验证

- 未把插件安装到真实 Orca（代理运行平台）用户环境，也未修改 Orca 配置或启动服务。
- 未验证真实 Orca 状态钩子产生事件后的完整运行过程。
- 未验证 iOS（苹果手机系统）实际订阅端收到通知；真实冒烟使用无人订阅的一次性随机主题。
