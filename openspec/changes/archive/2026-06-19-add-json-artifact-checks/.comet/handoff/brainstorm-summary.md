# Brainstorm Summary

- Change: add-json-artifact-checks
- Date: 2026-06-19
- Status: confirmed

## 确认的技术方案

为 Guard Point 增加独立 `json_artifact` check type。每个 check 表达一个 JSON 内容谓词，继续放在 `guard-points.yaml` 的 `checks` 列表中。Runtime 通过 artifacts.yaml 解析 artifact 路径，读取 JSON 后执行受限谓词；validator 在初始化前校验 check shape、artifact 引用和 predicate 合法性。

## 关键取舍与风险

- 取舍：不引入 JSONPath 或 JSON Schema，使用简单点路径和受限谓词，保持 Runtime 通用且可审计。
- 风险：复杂 JSON 查询能力不足。缓解：首版覆盖 review gate、metadata required、open findings 等已知场景，后续再扩展谓词。
- 风险：失败输出不够可定位。缓解：失败对象包含 artifact、field、predicate、expected、actual 和 reason，并进入 audit detail。

## 测试策略

- validator 测试：合法声明、缺 artifact、未知 artifact、缺 predicate、未知 predicate。
- runtime 测试：exists、equals、number_lte、number_gte、array_none、array_all、缺字段、非法 JSON、缺 artifact。
- 回归测试：现有 artifact_exists 行为和 override 行为不变。

## Spec Patch

无。当前 delta spec 已覆盖核心验收场景。
