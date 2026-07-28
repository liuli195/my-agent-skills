## ADDED Requirements

### Requirement: Release workflow template avoids deprecated Node action runtime
The release-flow generated GitHub Workflow template MUST use current GitHub Action versions that avoid Node.js 20 deprecation warnings where current replacements exist.

#### Scenario: Generated release workflow references are fully scanned
- **WHEN** release-flow validates its GitHub Workflow template
- **THEN** validation MUST inspect `uses:` action references and explicit Node runtime version declarations
- **THEN** every reference with an available current non-deprecated replacement MUST be upgraded or explicitly covered by an exception scenario

#### Scenario: Generated release workflow uses current checkout action
- **WHEN** release-flow generates or validates the release workflow template
- **THEN** the workflow MUST use `actions/checkout@v5`
- **THEN** the workflow MUST NOT use `actions/checkout@v4`
- **THEN** the workflow MUST keep the existing `workflow_dispatch` inputs and CI publish output contract
