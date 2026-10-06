## MODIFIED Requirements

### Requirement: Build and Verify has no root-level Python test configuration dependency
系统 MUST 不依赖根目录 Python（Python 语言）测试配置来定义本仓库 build（构建检查）或 verify（验证）行为。

#### Scenario: Root pyproject test config is absent
- **WHEN** 本仓库 build-and-verify（构建与验证）配置完成迁移
- **THEN** 根目录 `pyproject.toml` MUST NOT 存在
- **THEN** `.build-and-verify/config.json` 中的 pytest（Python 测试运行器）命令 MUST 显式声明测试路径和所需命令参数

#### Scenario: Explicit pytest commands cover repository tests
- **WHEN** 仓库 `tests/`（测试目录）包含 `test_*.py`（Python 测试文件）
- **THEN** `.build-and-verify/config.json` 中 pytest（Python 测试运行器）命令声明的测试文件集合 MUST 与该目录中的文件集合一致

#### Scenario: No root wrapper entrypoint
- **WHEN** 本仓库活跃自动化和 guard（守卫）命令文件被检查
- **THEN** 它们 MUST NOT 引用根目录测试 wrapper（包装入口）
- **THEN** 它们 MUST 引用仓库内 `.build-and-verify/runtime/build_and_verify.py` 或当前安装的 build-and-verify（构建与验证）Skill（技能）脚本
