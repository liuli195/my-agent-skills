## Why

`build-and-verify`（构建与验证）目前只有命令行 `init`（初始化）空模板，目标仓库要手写 `.build-and-verify/config.json`（配置文件）。这让通用仓库接入成本偏高，也容易让 `agent`（代理）临场自由发挥，生成不可复用或不可验证的配置。

## What Changes

- 新增 `build-and-verify-init`（构建与验证初始化）`Skill`（技能），作为 `agent`（代理）对话式初始化向导入口。
- 保持现有命令行 `init`（初始化）行为不变：仍只复制空配置模板、`.gitignore`（忽略规则）和本地 `cache`（缓存）目录。
- 将 `build-and-verify`（构建与验证）插件从单一 `Skill`（技能）入口改为两个入口：运行入口 `build-and-verify`（构建与验证）和初始化向导入口 `build-and-verify-init`（构建与验证初始化）。
- 初始化向导必须采用固定问答模板和渐进式披露参考文件，禁止 `agent`（代理）自由编造问题。
- 首版只识别 Node（节点运行时）和 Python（Python 语言）仓库迹象，并让用户选择纳入哪些 `check`（检查项）。
- 向导生成配置草案时必须在最终写入确认前展示摘要、覆盖风险、备份路径、定向依赖检查结果和用户可选的 `dry run`（试运行）范围。
- 覆盖已有 `.build-and-verify/config.json`（配置文件）前必须备份到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件），并确保 `/backups/` 被 `.build-and-verify/.gitignore`（忽略规则）忽略。
- 定向依赖检查发现问题时仍允许写入配置，但必须列明问题、影响和建议；只有用户授权后才处理依赖或环境问题。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `test-framework-plugin`: 更新 `build-and-verify`（构建与验证）插件的 `Skill`（技能）入口要求和初始化向导行为。

## Impact

- Affected plugin package: `plugins/build-and-verify/`（构建与验证插件）。
- Affected docs/specs: `openspec/specs/test-framework-plugin/spec.md`（规格）及本 change（变更）的 delta spec（规格增量）。
- Affected tests: `tests/test_build_and_verify_plugin.py`（构建与验证插件测试）。
- No dependency install, user-level config write, CI（持续集成） setup, or command-line `init`（初始化） behavior change is included.
