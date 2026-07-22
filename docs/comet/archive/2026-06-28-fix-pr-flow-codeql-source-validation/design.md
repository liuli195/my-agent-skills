## 根因

`validate_config`（校验配置）只把 required checks（必需检查）转成 Rulesets（规则集）远端待办，没有识别 `setup.github.codeScanning`（代码扫描建议）。因此 CodeQL（代码扫描）规则和扫描结果来源被当成同一件事。

## 修复方案

复用 `validate`（校验）已有 remote task（远端待办）输出，不新增远端写入能力。只检查本地 `.github/workflows` 中是否存在包含 `codeql-action` 的工作流文件；没有则输出“创建或启用 CodeQL 扫描结果来源”。

## 验证

新增两个测试：没有 CodeQL workflow（代码扫描工作流）时输出 remote task（远端待办）；已有 workflow（工作流）时不输出该待办。
