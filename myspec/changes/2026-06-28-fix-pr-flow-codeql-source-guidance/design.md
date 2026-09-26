## 根因

文档把 Rulesets rule（规则集规则）和 scan producer（扫描结果来源）合并成一个待办。实际 GitHub（代码托管平台）需要两者同时存在：规则负责要求结果，workflow（工作流）或默认设置负责产出结果。

## 修复方案

只补文档模板，不新增配置字段。CodeQL（代码扫描）开启时，远端待办同时说明：

- 配置 `Require code scanning results`（要求代码扫描结果）。
- 创建或启用 CodeQL scan producer（代码扫描结果来源）。

## 验证

扩展现有文档测试，锁定问答、草案和校验规则均包含扫描结果来源。
