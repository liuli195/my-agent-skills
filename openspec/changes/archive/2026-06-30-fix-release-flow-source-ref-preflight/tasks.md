## 1. 回归测试

- [x] 1.1 添加 `preflight`（发布前检查）拒绝远端 `sourceRef`（源引用）缺少版本提升的测试。

## 2. 实现修复

- [x] 2.1 在现有 `preflight_errors()`（发布前检查错误）中复用远端 manifest（清单）读取逻辑校验 `sourceRef`（源引用）。
- [x] 2.2 运行 release-flow（发布流程）相关测试和 OpenSpec（开放规格）校验。
