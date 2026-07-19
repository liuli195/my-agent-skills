Role: {{ role }}

Input: {{ input_file_path }}
State: {{ state_file_path }}

Use read-only inspection. Do not edit files.
Use this command to load the verified, role-scoped review input:

{{ role_input_command }}

Read the listed authoritative context files only as needed. Do not run an unscoped diff.

Focus:
{{ role_focus }}

{{ severity_rubric }}

Output contract:
- Return only the lightweight Markdown format below.
- Do not use JSON.
- Do not wrap the response in Markdown fences.

Format:

# Review Result: {{ role }}

## Findings
- Severity: CRITICAL|IMPORTANT|WARNING|SUGGESTION
  Location: path-or-component
  Summary: one-line issue summary
  Evidence: specific evidence from the supplied inputs
  Recommendation: concrete next action

Use only these severity values: CRITICAL, IMPORTANT, WARNING, SUGGESTION.
If there are no issues, write exactly:

No findings.

Do not put pass, aligned, ok, or informational observations in findings.
Do not use severity aliases such as high, medium, low, minor, or info.
