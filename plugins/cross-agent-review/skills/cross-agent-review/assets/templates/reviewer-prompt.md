Role: {{ role }}

Return only a single JSON object. Do not use Markdown.

Schema:

{{ schema_json }}

Use only these severity values: CRITICAL, IMPORTANT, WARNING, SUGGESTION.

If there are no issues, return "findings": [].

Do not put pass, aligned, ok, or informational observations in findings.

Do not use severity aliases such as high, medium, low, minor, or info.

{{ severity_rubric }}

{{ role_focus }}

Change: {{ change }}

Base ref: {{ base_ref }}

Head ref: {{ head_ref }}

Manifest file: {{ manifest_path }}

Use the referenced input files as the source of truth. Read only the sections needed for this review.

Use git diff/show/status read-only commands if the file references are insufficient.

{{ spec_reference }}

{{ design_reference }}

{{ tasks_reference }}
