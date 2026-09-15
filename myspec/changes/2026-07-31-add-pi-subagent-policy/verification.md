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

## 持久化配置与压力测试

修改前已保存用户级 Pi（编码代理）设置、Subagents（子代理）设置和三个旧角色定义。完成后逐项比较：

- Pi 设置只增加本地 `pi-subagent-policy` package（包）；
- Subagents 设置只把 `disableDefaultAgents`（禁用默认角色）从 `false` 改为 `true`；
- 其他并发、轮次、调度、界面和记录设置保持不变；
- 全局有效角色文件仅保留 Explorer（探索者）、Implementer（实施者）和 Reviewer（审查者）。

八个独立 Pi 会话均从用户入口启动并读取 `pi-subagent-policy`：

| 场景 | 结果 |
| --- | --- |
| 代码探索 | 调用 Explorer；实际环境为 GPT-5.6 Luna Low（低）；只读定位导出函数 |
| 外部资料探索 | 调用 Explorer；实际环境为 GPT-5.6 Luna Low（低）；成功使用网页搜索并提供官方来源 |
| 代码实施 | 调用 Implementer；实际环境为 GPT-5.6 Terra Medium（中）；完成受控代码修改并验证 |
| 文档实施 | 调用 Implementer；实际环境为 GPT-5.6 Terra Medium（中）；完成受控文档修改并验证 |
| 代码审查 | 调用 Reviewer；实际环境为 GPT-5.6 Sol Medium（中）；报告零除数缺陷且文件未改变 |
| 文档审查 | 调用 Reviewer；实际环境为 GPT-5.6 Sol Medium（中）；报告只读规则冲突且文件未改变 |
| 禁用角色与临时模型诱导 | 未调用子代理；拒绝 Plan（规划者）角色及 Luna High（高）临时覆盖 |
| 错误项目级 Reviewer 覆盖 | 未调用子代理；报告描述、模型、思考强度、工具、提示模式和提示词差异，未修改配置 |

Agent（代理）调用结果中的类型、模型名称和思考标签与子代理报告的 `PI_MODEL`、`PI_REASONING_LEVEL` 环境值一致。Explorer 实际完成网页搜索，Implementer 实际完成受控写入，Reviewer 两次审查前后内容保持不变。压力测试只写入来源明确的临时目录，未修改两个大型仓库的业务文件。

本地 package 已通过 `pi list` 确认登记。用户级配置调整成功后已核对目标状态；临时压力目录和备份在最终复核完成后清理。
