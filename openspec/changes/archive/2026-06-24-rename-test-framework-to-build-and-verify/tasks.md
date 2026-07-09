## 1. Rename Plugin Surface

- [x] 1.1 Move `plugins/test-framework` to `plugins/build-and-verify` and rename the Skill（技能） directory to `build-and-verify`.
- [x] 1.2 Update Claude（Claude 版本） and Codex（Codex 版本） plugin manifests to use `build-and-verify`（构建与验证） name and description.
- [x] 1.3 Rename `test_framework.py` and `test_framework_runner.py` to `build_and_verify.py` and `build_and_verify_runner.py`.
- [x] 1.4 Update Skill（技能） frontmatter（文件头） and usage text so all build（构建检查） and verify（验证） commands route through `build-and-verify`（构建与验证）.
- [x] 1.5 Keep the OpenSpec（开放规格） change modeled as a rename（改名） of the existing `test-framework-plugin`（测试框架插件） capability, not as a delete/add capability replacement.
- [x] 1.6 Keep implementation changes to rename（改名） and required reference updates; do not refactor（重构） or rewrite（重写） the existing test-framework（测试框架） logic.

## 2. Rename Configuration and Remove Extra Entrypoints

- [x] 2.1 Move `.test-framework` to `.build-and-verify` and update template paths, cache paths, and error messages.
- [x] 2.2 Delete root `pyproject.toml` and move its pytest（Python 测试运行器） behavior into explicit `.build-and-verify/config.json` commands.
- [x] 2.3 Ensure active automation, guard（守卫） command files, and configuration files do not reference root test wrapper（包装入口）, `.test-framework`, `test-framework`, or `test_framework.py`.

## 3. Update Repository Integrations

- [x] 3.1 Update `.comet.yaml` and `.comet/config.yaml` to call `build-and-verify`（构建与验证） build（构建检查） and default fast verify（快速验证） commands.
- [x] 3.2 Update `.pr-flow/config.yaml` hotfix（热修复） verification command to use `build-and-verify verify --full`（构建与验证完整验证）.
- [x] 3.3 Update marketplace（市场目录）, release projection（发布投影）, package tests, and plugin registration references.
- [x] 3.4 Update OpenSpec（开放规格） main specs and non-archived docs that describe current active commands.

## 4. Update Tests

- [x] 4.1 Rename test files, constants, fixture paths, command assertions, and cache path assertions from test-framework（测试框架） to build-and-verify（构建与验证）.
- [x] 4.2 Add or update tests that reject old `test-framework`（测试框架） active references and root `pyproject.toml`（Python 测试配置）.
- [x] 4.3 Add or update tests proving default verify（验证） stays fast（快速）, hotfix（热修复） uses explicit full（完整）, and other PR Flow（拉取请求流程） paths do not infer full verify（完整验证）.

## 5. Verification

- [x] 5.1 Run focused build-and-verify（构建与验证） plugin tests.
- [x] 5.2 Run local build command through `build-and-verify`（构建与验证）.
- [x] 5.3 Run default fast verify（快速验证） through `build-and-verify`（构建与验证）.
- [x] 5.4 Confirm this non-hotfix（非热修复） and non-PR-CI（非拉取请求持续集成） flow does not require `--full`（完整）; full verify（完整验证） remains limited to hotfix（热修复） direct push and PR CI（拉取请求持续集成）.
- [x] 5.5 Run `openspec validate rename-test-framework-to-build-and-verify --strict`.
