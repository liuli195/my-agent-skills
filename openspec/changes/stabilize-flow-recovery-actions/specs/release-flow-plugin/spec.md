## ADDED Requirements

### Requirement: Preflight failures expose ordered next actions
Release Flow preflight（发布预检） MUST translate known blocking errors into ordered next actions without changing publish（发布） behavior.

#### Scenario: Source ref missing version bump explains PR path
- **WHEN** preflight（发布预检） fails because `sourceRef`（源引用） does not contain the requested manifest（清单） version bump（版本提升）
- **THEN** output（输出） MUST identify that the version bump（版本提升） must first be merged through PR Flow（拉取请求流程）
- **THEN** output（输出） MUST include the ordered next action to create, merge, and then rerun preflight（发布预检）

#### Scenario: Manifest mismatch explains local correction
- **WHEN** preflight（发布预检） fails because a requested plugin manifest（插件清单） does not match the requested release version（发布版本）
- **THEN** output（输出） MUST identify the plugin（插件） and manifest（清单） path
- **THEN** output（输出） MUST include the next action to correct the manifest（清单） before rerunning preflight（发布预检）

#### Scenario: Existing release reports next version path
- **WHEN** preflight（发布预检） finds that the requested tag（标签） or GitHub Release（GitHub 发布） already exists
- **THEN** output（输出） MUST preserve `release already exists`（发布已存在）
- **THEN** output（输出） MUST include a next action to choose a new release version（发布版本） and rerun preflight（发布预检）
