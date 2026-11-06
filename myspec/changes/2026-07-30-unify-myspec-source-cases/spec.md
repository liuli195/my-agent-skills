# 统一 MySpec 客户端来源判定案例

**Status:** ready-for-agent

## Problem Statement

MySpec（自有规格）需要判断 Pi、Claude 和 Codex 中的来源是否已安装、已注册、已启用并实际生效。当前三端分别解释各自客户端输出，缺少共同的来源状态语言和可执行案例，导致相同概念在不同适配中含义不一致。

Pi 适配已经连续修复配置读取、项目信任、来源诊断、实际来源、相对路径和安装目录缺失等同类问题。现有测试虽然覆盖许多单端场景，但没有一个三端必须共同运行的案例集合，因此新增或修改来源状态时，无法证明三端仍遵守同一语义。

诊断输出也尚未为三端提供统一的来源列表。部分顶层字段混合了“已登记”“文件存在”“配置允许加载”和“当前实际生效”等不同事实，使目录缺失、来源覆盖或错误来源等状态难以准确表达。

## Solution

建立一个独立的共享 JSON（数据文件）案例表，定义三端共同的来源状态、输入场景和期望结果。Pi、Claude 和 Codex 的测试必须读取同一份案例表，将每个案例转换成各自客户端的原生状态，并通过打包后的 `myspec doctor`（诊断命令）完整入口验证公开结果。

统一六项来源语义：

- `installed`（已安装）：宿主报告了安装位置，并且该目录实际存在且包含可识别的 MySpec 包信息。
- `registered`（已注册）：宿主已经识别并登记该来源；不代表它已安装、已启用或实际生效。
- `enabled`（已启用）：宿主配置允许加载该来源；即使安装目录缺失，该配置意图仍然成立。
- `effective`（实际生效）：来源已注册、已安装、已启用，并且未被更高优先级来源覆盖。
- `sourceKind`（来源类型）：只对 MySpec 来源使用 `stable`（稳定来源）或 `legacy`（旧版来源）；无关来源不进入 MySpec 来源列表。
- `sourceMismatch`（来源不匹配）：宿主登记了目标 MySpec 标识，但它解析到的来源与当前期望来源不同。旧版来源本身不构成来源不匹配。

三端的 `doctor`（诊断命令）结果统一公开 `sources[]`（来源列表），其中每项提供上述六项结果及识别该来源所需的现有公开信息。现有顶层诊断字段继续保留，避免破坏已有调用方。

共享案例表先固定六个核心案例：无来源、稳定来源正常启用、稳定来源被禁用、稳定来源目录缺失、旧版来源正常启用、目标标识指向错误来源。三端必须运行全部核心案例。相对路径、Pi 项目覆盖、重复来源及其他宿主特有机制继续由各端专属测试覆盖，不伪造成并不存在的跨宿主能力。

## User Stories

1. As a MySpec user, I want Pi、Claude and Codex to use the same source-state meanings, so that diagnosis is consistent across clients.
2. As a MySpec user, I want registration to be reported independently from installation, so that a registered source with missing files can be diagnosed accurately.
3. As a MySpec user, I want enabled configuration to remain visible when an installation directory is missing, so that configuration intent is not concealed by a filesystem failure.
4. As a MySpec user, I want effective state to account for registration, installation, enablement and source precedence, so that the report identifies what can actually load.
5. As a MySpec user, I want stable and legacy sources distinguished, so that migration state is visible without treating every old source as an unrelated error.
6. As a MySpec user, I want a target identifier that points to the wrong source reported as a mismatch, so that stale or incorrect marketplace registration is obvious.
7. As a MySpec user, I want unrelated plugins and packages excluded from MySpec source results, so that the diagnosis stays focused.
8. As a Pi user, I want project-level source precedence represented through the shared effective-state meaning, so that project overrides do not produce a false active user source.
9. As a Pi user, I want relative paths resolved using the settings file that owns them, so that user and project settings remain deterministic.
10. As a Claude user, I want marketplace registration, plugin installation and plugin enablement represented as separate facts, so that a stale marketplace or disabled plugin is distinguishable.
11. As a Codex user, I want marketplace registration, cached installation and configured enablement represented as separate facts, so that missing cache content is not reported as healthy.
12. As a maintainer, I want one executable source-case table, so that a new shared state is defined once rather than copied into three test suites.
13. As a maintainer, I want every shared case executed by all three clients, so that one adapter cannot silently diverge from the common contract.
14. As a maintainer, I want shared cases to use each client's native output shape, so that tests exercise parsing and mapping rather than only testing abstract helper functions.
15. As a maintainer, I want tests to invoke the packaged command-line entry, so that package contents, client invocation and public output are verified together.
16. As a maintainer, I want host-specific cases to remain separate, so that the shared model does not invent capabilities that Claude or Codex do not provide.
17. As an existing caller of `myspec doctor`, I want current top-level fields retained, so that adding normalized source records does not break existing automation.
18. As a future contributor, I want a new shared source state to require a new case and expected result before adapter code changes, so that the contract leads implementation.
19. As a reviewer, I want the six canonical terms documented in the repository glossary, so that code, tests and issue descriptions use the same language.
20. As a reviewer, I want a public diagnostic contract backed by an architectural decision, so that later changes preserve the reason for shared cases and compatible output.

## Implementation Decisions

- The shared contract is a host-neutral source-state model, not a shared production parser. Pi、Claude and Codex retain separate adapters for their native client output.
- One independent JSON（数据文件） contains the shared core cases and expected six-field results. It is executable test data rather than a prose-only table or a language-specific constant.
- Every core case has a stable identifier. Adding a shared source state begins by adding or changing a case and its expected result before adapter behavior is changed.
- The initial shared core cases are exactly: no source; stable source installed and enabled; stable source installed but disabled; stable source registered and configured enabled with a missing installation directory; enabled legacy source; and the target identifier resolving to an incorrect source.
- Pi、Claude and Codex test adapters translate each shared case into the client's real command-output shape. The shared file does not contain three copies of native client payloads.
- `registered` means the host recognizes and records the source. It is independent of installation, enablement and effectiveness. Pi behavior that currently derives registration from available skills must be corrected.
- `installed` requires both a host-reported installation location and an existing recognizable MySpec package directory. A configured path, cache record or missing directory alone is not installed.
- `enabled` reports host configuration intent independently of installation and effectiveness.
- `effective` requires registered, installed and enabled state and requires the source to survive host precedence or override rules.
- `sourceKind` accepts only `stable` and `legacy` for recognized MySpec sources. Unrelated sources are excluded rather than assigned an `unknown`（未知） type.
- `sourceMismatch` applies when the canonical target registration resolves somewhere other than the expected current source. A recognized legacy source is represented through `sourceKind` and is not automatically a mismatch.
- Pi、Claude and Codex diagnostic sections each expose `sources[]` with the common six fields. Existing source identifiers, paths or scope data needed to identify records remain available alongside them.
- Existing top-level diagnostic fields remain available for compatibility. Their values must not contradict the canonical source records.
- Host-specific behavior remains in host-specific tests. This includes relative-path resolution and project precedence where the host exposes those mechanisms.
- The six canonical source terms are added to the domain glossary without implementation details.
- The shared executable contract, separate native adapters and compatibility-preserving output extension are recorded in an ADR（架构决策记录） because they define a public contract and a deliberate alternative to a shared parser.
- This work addresses GitHub Issue（GitHub 问题）#218.

## Testing Decisions

- Tests assert public behavior only: packaged command execution, client-facing state conversion and the resulting `doctor`（诊断命令） JSON（数据）. They do not call private source-classification helpers directly.
- The single primary test seam is the existing packed npm Tarball（npm 软件包） installed into an isolated environment. Tests invoke the installed `myspec doctor` command as a user would.
- Existing controlled Pi、Claude and Codex executable substitutes remain the native client boundary. Each substitute receives state generated from the same shared case and emits the client's real output structure.
- A three-client parameterized regression runs every shared case against Pi、Claude and Codex and compares the normalized `sources[]` record with the shared expected six fields.
- The regression must prove that all three adapters consumed every shared case identifier; separate look-alike case lists do not satisfy the contract.
- The missing-directory case creates the host record and enabled configuration but omits the package directory, proving that registered and enabled remain true while installed and effective are false.
- The mismatch case registers the canonical target identifier against a different valid source and proves that mismatch is true while the expected stable source is not effective.
- Existing Pi relative-path, project-precedence, duplicate-source and missing-installed-path regressions remain and are aligned with the canonical field meanings.
- Existing Claude and Codex marketplace, disabled-plugin, stale-source and missing-installation regressions remain and are aligned with the canonical field meanings.
- Tests verify that existing top-level fields remain present and are consistent with `sources[]`.
- Complete verification uses the repository's Build and Verify（构建与验证） entry and includes the packed end-to-end flow rather than replacing it with isolated unit tests.
- Prior art is the existing packed MySpec subprocess suite and its controlled Pi、Claude and Codex executables. No new test framework or internal testing seam is introduced.

## Out of Scope

- Replacing the three native client adapters with one generic production parser.
- Making Claude or Codex emulate Pi project settings or project precedence.
- Moving every existing host-specific case into the shared JSON（数据文件）.
- Enumerating every possible combination of the six source fields.
- Assigning `sourceKind=unknown`（未知） to unrelated sources.
- Removing or renaming existing top-level `doctor`（诊断命令） fields.
- Changing installation, update or mode-switch behavior except where necessary to make diagnosis obey the agreed source semantics.
- Adding support for clients other than Pi、Claude and Codex.
- Installing or modifying real machine-level client state as part of automated tests.

## Further Notes

- The shared table is intentionally small. It defines the cross-client semantic floor; host-specific tests continue to carry client-specific risk.
- A source can be registered and enabled while not installed. This is a valid diagnostic state, not an invalid combination to normalize away.
- A legacy source can be effective. Migration policy may later disable it, but source classification and current effectiveness remain separate facts.
- `sources[]` is the canonical detailed view. Compatibility fields are projections and should be derived or checked against the same observations to prevent renewed semantic drift.
