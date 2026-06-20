## MODIFIED Requirements

### Requirement: Global Command Guard built-in context values

Global Command Guard MUST expose generic built-in context values for template rendering and JSON `value_from` checks.

#### Scenario: Short Git HEAD is available

- **WHEN** Runtime evaluates a Global Command Guard inside a Git repository
- **THEN** `git_head` MUST contain the full current HEAD
- **AND** `git_head_short` MUST contain the first 12 characters of `git_head`
- **AND** `git_head_short` MUST be allowed in artifact path templates and JSON `value_from` checks
