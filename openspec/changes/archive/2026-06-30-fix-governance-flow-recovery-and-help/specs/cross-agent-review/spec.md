## ADDED Requirements

### Requirement: head_ref_short path convention is explicit
系统 MUST 明确 `head_ref_short`（短头引用）等于 `head_ref`（头引用）的前 12 个字符，并在 cross-agent-review（跨代理审查）的用户可见路径中保持一致。

#### Scenario: Review input path uses first 12 characters
- **WHEN** 调用方准备 `review-input.json`（审查输入文件）
- **THEN** `<head_ref_short>`（短头引用） MUST equal the first 12 characters of `head_ref`（头引用）
- **THEN** the input path（输入路径） MUST be `.local/cross-agent-review/<change>/<head_ref_short>/prepared-inputs/review-input.json`

#### Scenario: Run output prints copyable review input path
- **WHEN** `cross-agent-review run`（跨代理审查运行） accepts an input file（输入文件）
- **THEN** output（输出） MUST include the copyable `review-input.json`（审查输入文件） path used for the run
- **THEN** output（输出） MUST expose the same 12-character `head_ref_short`（短头引用） value

#### Scenario: Mark-pass output uses the same short reference
- **WHEN** `mark-pass`（标记通过） writes pass marker（通过标记）
- **THEN** the evidence path（证据路径） MUST use the same 12-character `head_ref_short`（短头引用）
- **THEN** output（输出） MUST include the copyable evidence path（证据路径）
