# Acceptance evidence

<!-- comet-native:acceptance-evidence:start -->
[
  {
    "acceptance_id": "acceptance-3b61020e0c9f53d7f1484ccb9c8bc1cc519b6b398ef295f0afceccd4c65ca1a8",
    "evidence_refs": [
      "tests/pi_cache_diagnostics.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-4f8099384c07ee211ce891c1e82eb858254df49555f023e3bb2b4e3c2a1332b0",
    "evidence_refs": [],
    "skipped_reason": "未能在不增加测试专用注入接口的情况下稳定触发 Gzip 压缩失败。"
  },
  {
    "acceptance_id": "acceptance-7ff3475a656cb660c4e7c87df1673a2182e07fd0a3b767245289149ef1589d54",
    "evidence_refs": [
      "plugins/pi-cache-diagnostics/extensions/pi-cache-diagnostics.ts",
      "tests/pi_cache_diagnostics.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-9865400dd349ec0bd3276297bf7c819a8737516ef2e984ecf119c16eb7b10b2c",
    "evidence_refs": [
      "tests/pi_cache_diagnostics.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-c239097fd5dc8620477b6d46b6a81ae9c834cacc125cbd2a083a75ae36f3c69d",
    "evidence_refs": [
      "tests/pi_cache_diagnostics.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-cc4a402dca2c997694f3226bd272670b986451376659a07a7b2a01fe44906b60",
    "evidence_refs": [
      "tests/pi_cache_diagnostics.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-d5f7dc554d1125985fae32a73e0e792149e55524a65aed4c626665528ca36ee1",
    "evidence_refs": [],
    "skipped_reason": "OpenAI Codex 内部自动重试没有逐次公开事件，未进行真实网络故障注入。"
  },
  {
    "acceptance_id": "acceptance-e967604ec239c98c1b3237553119fc8a35d9de23c6b5013162606b8f9203c76a",
    "evidence_refs": [
      "tests/pi_cache_diagnostics.test.mjs"
    ]
  }
]
<!-- comet-native:acceptance-evidence:end -->

# Commands and results

- `python .build-and-verify/runtime/build_and_verify.py build --project .`：通过。
- `python .build-and-verify/runtime/build_and_verify.py verify --project .`：通过；69 个仓库测试与 `pi-cache-diagnostics`（Pi 缓存诊断插件）扩展入口回归通过。

# Skipped checks

- 未向真实 OpenAI Codex（模型服务）注入网络失败，因此未验证其内部自动重试；公开接口本身也不提供逐次完整传输事件。
- 未稳定注入 Gzip（压缩格式）失败；已检查保留 `.jsonl.failed` 和失败开放实现路径，但不把代码检查写成运行通过。
- 未执行 `--full`（完整）验证，因为本流程不属于获准使用完整模式的 PR（拉取请求）或 hotfix（热修复）场景。

# Spec consistency

实现直接加载并调用 Pi（编码代理）内部 `detectCacheMiss`（缓存未命中检测），删除插件自有检测、差异与大型 Miss（大型未命中）逻辑。扩展入口回归验证了正常命中、原生 Miss（未命中）、自包含压缩证据、敏感头过滤、重新加载检查点、历史分支证据边界和压缩重置。

# Known limitations and risks

- 当前仅支持 `openai-codex`（OpenAI Codex 模型服务）。
- Pi（编码代理）内部模块路径不是公开扩展接口，升级后需同步检查。
- `observedProviderPayload`（观测到的模型服务载荷）可能被后续扩展继续修改。
- 内部网络重试不可逐次观测。
- 压缩失败与真实网络重试两个故障场景未完成端到端注入。

# Conclusion

快速构建和验证通过，已覆盖主要扩展入口流程。结论为通过，但保留两个明确未验证的故障注入场景，不宣称完整覆盖。