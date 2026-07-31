# 验证记录

## TDD（测试驱动开发）

- Red（失败）：目标 package（包）不存在时，Pi 公开的 Skill（技能）发现接口报告缺少 `pi-subagent-policy`。
- Green（通过）：实现后，同一发现检查确认该 Skill 可被模型调用；角色契约检查同时通过。

## Pi 用户入口

通过 `pi --skill <skill-directory> --no-session --mode json --print <delegation-request>` 启动真实 Pi（编码代理）会话。会话记录证明：

- 主 Agent（代理）自动读取 `pi-subagent-policy`；
- 主 Agent 检查项目级与全局子代理配置；
- 当前配置缺少正式角色且默认角色仍启用时，主 Agent 明确报告差异；
- 主 Agent 没有启动子代理，也没有修改配置。

保留的 Node.js（运行时）回归通过 Pi 的 `DefaultResourceLoader`（默认资源加载器）从内存设置中的本地 package 路径加载 Skill，并确认来源为 `package`。另通过隔离的 `PI_CODING_AGENT_DIR`（Pi 配置目录）执行 `pi install <local-package-directory>` 和 `pi list`，确认 Pi 可直接登记该本地 package。隔离目录随后清理，用户级配置未改变。

## 仓库验证

- Build and Verify（构建与验证）构建检查：通过。
- Build and Verify 快速验证：通过修正跨语言测试边界后通过。
- Build and Verify 完整验证：全部检查通过；总耗时超过仓库性能预算，已生成性能报告，但功能验证状态为通过。

票据 02 的用户级配置安装和八会话压力测试仍未执行。
