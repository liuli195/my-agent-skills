## MODIFIED Requirements

### Requirement: Runtime Router focus handling
The system MUST preserve existing Session Focus permission semantics. A Global Command Guard MUST add only an independent pre-check at the `PreToolUse` entrypoint, and an allowed result without an active session focus MUST NOT write an audit file.

#### Scenario: Global command guard runs before session-focus permissions
- **WHEN** a command matches both a Global Command Guard and a Session Focus permission rule
- **THEN** the Runtime evaluates the Global Command Guard first
- **AND** the command does not execute when either check returns deny

#### Scenario: Allowed global guard continues to session-focus permissions
- **WHEN** a Global Command Guard allows a command
- **AND** a Session Focus permission rule exists
- **THEN** the Runtime continues with the existing Session Focus permission check

#### Scenario: Global guard does not modify session focus
- **WHEN** a Global Command Guard allows or denies a command
- **THEN** the Runtime does not write, replace, or remove the Session Focus Binding

#### Scenario: Allow without an active session focus
- **WHEN** the `PreToolUse` entrypoint has no active Session Focus Instance and continues execution
- **THEN** the Runtime returns `status=allow` and `reason=no_session_focus_instance`
- **AND** the Runtime does not write an audit file or include `audit_path` in the result

#### Scenario: Block without an active session focus
- **WHEN** an entrypoint that requires an active Session Focus Instance has no active focus
- **THEN** the Runtime stops the operation and retains the `no_session_focus_instance` audit
