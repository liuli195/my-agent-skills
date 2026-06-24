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

Review subject commands:

{{ review_subject_commands }}

Changed files:

{{ changed_files }}

Context files:

{{ context_files }}

Use the manifest and referenced context files as the source of truth.

Read only the context file sections needed for this review.

Do not read a complete diff output.

Use path-scoped diffs for changed paths:

{{ path_diff_command_template }}
