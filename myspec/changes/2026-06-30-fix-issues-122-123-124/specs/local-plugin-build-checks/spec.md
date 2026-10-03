## ADDED Requirements

### Requirement: Repository workflows avoid deprecated Node runtime references
The repository's active GitHub workflows MUST avoid Node.js 20 action/runtime references when a current replacement is available.

#### Scenario: Active workflow references are fully scanned
- **WHEN** repository workflow validation runs
- **THEN** it MUST inspect every active `.github/workflows/*.yml` file
- **THEN** it MUST inspect `uses:` action references and explicit Node runtime version declarations
- **THEN** every reference with an available current non-deprecated replacement MUST be upgraded or explicitly covered by an exception scenario

#### Scenario: Checkout actions use current major
- **WHEN** active `.github/workflows/*.yml` files are inspected
- **THEN** each `actions/checkout` reference MUST use `actions/checkout@v5`
- **THEN** no active workflow MUST reference `actions/checkout@v4`

#### Scenario: Full verify uses current setup actions and Node runtime
- **WHEN** `.github/workflows/full-verify.yml` is inspected
- **THEN** it MUST use `actions/setup-node@v6`
- **THEN** it MUST use `node-version: "24"`
- **THEN** it MUST use `actions/setup-python@v6`

#### Scenario: CodeQL action stays on current available major
- **WHEN** `.github/workflows/codeql.yml` is inspected
- **THEN** `github/codeql-action/init` and `github/codeql-action/analyze` MAY remain on `@v4` while no newer major is available
