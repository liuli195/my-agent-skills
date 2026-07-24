## 1. Init Skill Flow

- [x] 1.1 Update `pr-flow-init` Skill（初始化技能） to describe agent（代理）问答、草案展示、校验、用户确认和写入边界。
- [x] 1.2 Restructure `pr-flow-init` Skill（初始化技能） for progressive disclosure（渐进式披露）: hard boundaries（硬边界）, closed loop（闭环）, required flow（必需流程）, output（输出） and `references/`（参考文件） list only.
- [x] 1.3 Add `references/questionnaire.md`（问答模板） with fixed questions, fixed options, selection consequences and jump rules.
- [x] 1.4 Organize PR Flow init（拉取请求流程初始化）Plugin（插件）/Skill（技能） content and `references/`（参考文件） by user scenario: first-time enablement（初次启用）, review gate（审查门禁）, hotfix（热修复）, cleanup（清理）, GitHub setup suggestions（GitHub 配置建议） and final write confirmation（最终写入确认）.
- [x] 1.5 Add `references/config-draft.md`（配置草案规则） for `.pr-flow/config.yaml`（配置文件） shape, defaults（默认配置）, branch overrides（分支覆盖） and `setup.github`（GitHub 配置建议）.
- [x] 1.6 Add `references/validation.md`（校验规则） for dependency matrix（依赖矩阵）, validation output（校验输出） and write summary（写入摘要）.
- [x] 1.7 Keep existing PR Flow（拉取请求流程） command boundaries in the Skill（技能） text: no commit（提交）, push（推送）, merge（合并）, or GitHub API（GitHub 接口） writes during init（初始化）.

## 2. Config Validation

- [x] 2.1 Add `validate`（校验） command parsing with `--config <path>`（配置文件路径）.
- [x] 2.2 Implement read-only YAML（配置格式） loading and structured output for error（错误）, warning（警告）, and setup suggestion（配置建议）.
- [x] 2.3 Validate core shape and allowed values for `defaults`（默认配置）, `branches`（分支配置）, `reviewGate`（审查门禁）, `wait`（等待设置）, `hotfix`（热修复）, `authorization`（授权短语） and `setup.github`（GitHub 配置建议）.
- [x] 2.4 Validate hotfix（热修复） dependencies: allow-list（允许列表）, authorization phrase（授权短语）, verify command（验证命令）, remote（远端名） and Rulesets bypass（规则集绕过权限） suggestion.
- [x] 2.5 Validate review gate（审查门禁）, checks（检查）, merge strategy（合并方式）, cleanup（清理） and tweak（小改） dependency warnings.
- [x] 2.6 Preserve fast/full verify（快速/完整验证） boundary checks in validation output.
- [x] 2.7 Ensure validate（校验） errors block init（初始化） writes; warnings（警告） and setup suggestions（配置建议） only require display before confirmation.

## 3. Init Write Path

- [x] 3.1 Keep `init`（初始化） script（脚本） able to write `.pr-flow/config.yaml`（配置文件）, PR template（拉取请求模板） and `.pr-flow/.gitignore`（忽略文件）.
- [x] 3.2 Add a confirmed-config input path for init（初始化）, reusing validate（校验） before write.
- [x] 3.3 Reject or make non-writing any old default init（初始化） call that lacks confirmed config input; do not silently write generated defaults from `--base-branch`（目标分支参数） alone.
- [x] 3.4 Ensure init（初始化） never performs terminal prompts（终端提示）, GitHub API（GitHub 接口） writes, or flow dry runs（试运行）.

## 4. Tests And Verification

- [x] 4.1 Update PR Flow CLI（命令行接口） tests for validate（校验） success and failure output.
- [x] 4.2 Add dependency matrix tests for hotfix（热修复）, review gate（审查门禁）, checks（检查）, merge strategy（合并方式）, cleanup（清理） and tweak（小改）.
- [x] 4.3 Update init（初始化） tests to cover confirmed config write path and old default write rejection.
- [x] 4.4 Update package or Skill（技能） tests to ensure `pr-flow-init` documents agent（代理）问答 rather than script（脚本） terminal interaction.
- [x] 4.5 Add tests that require `pr-flow-init/references/questionnaire.md`, `config-draft.md` and `validation.md`（问答模板、配置草案规则、校验规则） to exist and be referenced by the Skill（技能） entrypoint.
- [x] 4.6 Add tests that Plugin（插件）/Skill（技能） content is organized by user scenario, and questionnaire（问答模板） contains fixed questions, fixed options, consequences and jump rules.
- [x] 4.7 Add an end-to-end regression from `pr-flow-init` Skill（初始化技能） entrypoint: load references（参考文件）, simulate fixed questionnaire（问答模板） answers and final confirmation, generate draft, run read-only validate（校验）, write via confirmed config input, and perform post-write structure check without running diagnose、complete、cleanup、hotfix or tweak（诊断、收尾、清理、热修复、小改）.
- [x] 4.8 Run focused PR Flow（拉取请求流程） tests and OpenSpec（开放规格） strict validation.

## 5. Cross-Agent Review And Guard Evidence

- [x] 5.1 Simplify cross-agent-review（跨代理审查） output to Markdown（标记文本） `review-report.md`（审查报告） and remove automatic `review-pass.json`（审查通过文件） generation.
- [x] 5.2 Define severity（严重级别） values `CRITICAL`、`IMPORTANT`、`WARNING` and `SUGGESTION`, and require main agent（主代理） semantic pass/fail judgment.
- [x] 5.3 Add `mark-pass`（标记通过） to write guard-defined evidence（守卫定义证据） under `.local/guard/evidence/<profile_id>/cross_agent_review_pass/<change>/<head_ref_short>/pass.json`.
- [x] 5.4 Update Agent Guard（代理守卫） runtime, skill references, specs and tests so `cross_agent_review_pass` uses the unified guard evidence（守卫证据） path.
- [x] 5.5 Keep plugin-owned SDK（开发包） timeout（超时） at 480 seconds per reviewer（审查代理） and 540 seconds per dispatch（派发）, while forbidding an extra shorter main-agent timeout/watchdog（主代理超时/看门等待） wrapper.
- [x] 5.6 Run focused cross-agent-review（跨代理审查） and Agent Guard（代理守卫） tests, OpenSpec（开放规格） strict validation, diff check（差异检查） and full pytest（测试） regression.
