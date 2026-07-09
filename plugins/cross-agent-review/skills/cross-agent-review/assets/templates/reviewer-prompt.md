Role: {{ role }}

Read: {{ input_file_path }}

Use read-only inspection. Do not edit files.
Review only base_ref...head_ref from the input file.
Use spec_file, design_file, and plan_file as requirements context.

Output contract:
- Return only the lightweight Markdown format below.
- Do not use JSON.
- Do not wrap the response in Markdown fences.

Review commands:

{{ review_subject_commands }}

Focus:
{{ role_focus }}

{{ severity_rubric }}

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
