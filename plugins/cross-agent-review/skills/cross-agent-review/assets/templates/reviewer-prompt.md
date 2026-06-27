Role: {{ role }}

Read: {{ input_file_path }}

Use read-only inspection. Do not edit files.
Review only base_ref...head_ref from the input file.
Use spec_file, design_file, and plan_file as requirements context.

Output contract:
- Your entire final response MUST be exactly one JSON object.
- The first character of the response MUST be `{`.
- The last character of the response MUST be `}`.
- Do not write any preface, explanation, summary, or conclusion outside the JSON object.
- Do not wrap the JSON object in Markdown fences.

Review commands:

{{ review_subject_commands }}

Focus:
{{ role_focus }}

{{ severity_rubric }}

Return only a single JSON object. Do not use Markdown.

Schema:

{{ schema_json }}

Use only these severity values: CRITICAL, IMPORTANT, WARNING, SUGGESTION.
If there are no issues, return "findings": [].
Do not put pass, aligned, ok, or informational observations in findings.
Do not use severity aliases such as high, medium, low, minor, or info.
