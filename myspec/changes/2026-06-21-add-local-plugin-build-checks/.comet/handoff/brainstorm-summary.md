# Brainstorm Summary

- Change: add-local-plugin-build-checks
- Date: 2026-06-21

## 确认的技术方案

已确认：新增 `scripts/check.py` 作为统一入口，提供 `build` 和 `verify` 两个子命令。

- `build` 负责本地插件包成型检查：Claude（Claude 编码工具）本地校验、Claude marketplace（插件市场目录）结构、Codex（OpenAI 编码代理）插件清单、release-flow projection（发布流程投影）一致性、Guard Profile（守卫画像）模板镜像一致性。
- `verify` 负责完整 Python（Python 语言）测试：调用 `python -m pytest`，由 `pyproject.toml` 中的 pytest（Python 测试框架）配置决定默认发现范围。
- `.comet/config.yaml` 只配置仓库入口：`python scripts/check.py build` 和 `python scripts/check.py verify`。
- `.comet/build-check.sh` 不再作为正式入口；执行阶段先查引用，若无引用则删除。

## 候选方案

### 方案 A：统一 Python 检查入口（推荐）

用 `scripts/check.py` 封装所有本地检查。

优点：跨 Windows（微软系统）和 Git Bash（Git 命令行环境）更稳定；错误信息可控；后续容易扩展。
缺点：需要新增一层脚本和对应测试。

### 方案 B：直接在 `.comet/config.yaml` 写 shell 命令

把 Claude 校验、pytest 和其他检查直接串在 `build_command` / `verify_command` 中。

优点：文件少。
缺点：Windows 路径和 shell 差异更脆弱；本仓库自定义一致性检查不好表达；测试困难。

### 方案 C：复用 `.comet/build-check.sh`

继续扩展历史脚本。

优点：已有文件。
缺点：它是历史临时脚本，且当前只跑部分测试；继续扩展会固化误导性的构建入口。

## 关键取舍与风险

- 不启用 `claude plugin validate --strict`（严格校验）：当前仓库已有 warning（警告），strict 会失败；先保证 build 可用，strict 清理另做。
- build 不跑完整 pytest：避免构建阶段过重；完整测试放入 verify。
- build 不访问 GitHub（代码托管平台）远端、不发布、不安装、不写用户配置：保证本地可重复、无副作用。
- Guard Profile 模板只做镜像字节一致性检查，不做语义判断。
- Claude CLI 缺失会导致 build 失败；错误信息必须明确提示缺少 Claude CLI。

## 测试策略

- 使用测试优先方式为 `scripts/check.py build` 写单元测试，覆盖：
  - 自动读取 `.claude-plugin/marketplace.json`
  - 调用 Claude plugin validate
  - marketplace source（来源路径）越界/缺失失败
  - marketplace 名称与 manifest（清单）名称不一致失败
  - Codex manifest 必填字段和路径缺失失败
  - release-flow projection 插件集合不一致或重复失败
  - Guard Profile 模板镜像不一致失败
- 为 `scripts/check.py verify` 写测试，确认它调用 `python -m pytest`。
- 为 `.comet/config.yaml` 写配置测试，确认 Comet 使用新入口。
- 最终运行 `python scripts/check.py build` 和 `python scripts/check.py verify`。

## Spec Patch

无。
