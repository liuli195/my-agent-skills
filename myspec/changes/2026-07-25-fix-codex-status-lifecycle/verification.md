# Acceptance evidence

<!-- comet-native:acceptance-evidence:start -->
[
  {
    "acceptance_id": "acceptance-486e9328dba7bb743fd38251a396b00c4506fccc56c46e9c5b157307abb333bc",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-6e599a596ae0c230063ec3b8c9fe8307a1c00518f98abdb46a9647d965236bce",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-86fcb886c9012ce2afd4b867f729b224ed7070d8efcd735fe27d2b5f0e39d335",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-acccfae9ce9228eaa438c1f8c0ba2e1ad429fde553e4dae8896c2f76196e028b",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/pi_codex_usage_status.test.mjs"
    ]
  }
]
<!-- comet-native:acceptance-evidence:end -->

# Commands and results

- `node tests/pi_codex_usage_status.test.mjs`：通过；包含故障实现红灯、远程过程调用生命周期回归和真实 Pi `/reload` 终端回归。
- `python .build-and-verify/runtime/build_and_verify.py build --project .`：通过。
- `python .build-and-verify/runtime/build_and_verify.py verify --project .`：通过，69 项检查通过。
- `git diff --check`：通过；仅有现有换行转换提醒。

# Skipped checks

- 未运行完整验证；仓库规则未授权本任务使用完整模式。
- 未安装到用户环境；测试从仓库插件发布形态加载。

# Spec consistency

所有状态栏写入均经过同一个安全函数；计时器、请求取消和代次检查保持不变，没有引入新的运行环境架构。

# Known limitations and risks

Pi 没有公开运行环境有效性查询，因此状态写入仍需捕获失效 UI 异常；该异常现已在唯一写入点隔离，而不是依赖刷新 Promise 的外围兜底。

# Conclusion

通过。真实 `/reload` 后 Pi 保持运行，新扩展实例恢复状态刷新，会话关闭安全清除状态。
