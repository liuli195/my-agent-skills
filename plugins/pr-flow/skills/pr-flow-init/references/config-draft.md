# PR Flow Init Config Draft

## 场景：运行配置

草案 MUST 使用 `defaults`（默认配置）加 `branches`（分支覆盖）。

```yaml
defaults:
  baseBranch: main
  mergeStrategy: merge
  reviewGate:
    mode: github
    evidencePath: .pr-flow/review-pass.json
  hotfix:
    verifyCommand: python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full
  wait:
    timeoutSeconds: 600
    pollSeconds: 15
  pr:
    bodyTemplatePath: .pr-flow/pr-template.md
    requiredSections:
      - Summary
      - Scope
      - Verification
      - Risk
      - Rollback
branches:
  main:
    remote: origin
    allowHotfixPush: false
```

## 场景：GitHub setup suggestions（GitHub 配置建议）

`setup.github`（GitHub 配置建议）MAY include protected branches（受保护分支）、required checks（必需检查）、required review（必需审查）、allowed merge methods（允许合并方式）、auto-delete head branch（自动删除源分支）和 Rulesets bypass（规则集绕过权限）。

`setup.github`（GitHub 配置建议）MUST NOT be consumed by diagnose、complete、cleanup、hotfix or tweak（诊断、收尾、清理、热修复、小改）。
