# Commands and results

通过。实现与已确认规格一致。

- `pi -e ./plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts --list-models`：通过，扩展入口可加载。
- `node tests/pi_codex_usage_status.test.mjs`：通过，覆盖 7 天窗口选择、显示格式、取整、重置状态及刷新间隔。
- `python -m pytest -q -p no:cacheprovider tests/test_pi_codex_usage_status.py`：通过，1 项检查通过。
- `python .build-and-verify/runtime/build_and_verify.py build --project .`：通过。
- `python .build-and-verify/runtime/build_and_verify.py verify --project .`：通过；相关两组共 275 项检查通过。
- 从 Pi RPC（远程过程调用）入口加载扩展并保持会话 10 秒：成功通过真实 Codex API（应用程序接口）取得额度，发出 `mcp-codex` 状态 `Codex：47%/6D4H`；退出时清理状态。
- `git diff --check`：通过。

# Skipped checks

- 未执行 `--full`（完整验证）；仓库规则仅允许明确授权的特定场景执行。
- 未安装到用户环境；这是明确非目标。

# Spec consistency

实现覆盖 14 项验收行为，与 brief（需求摘要）和完整目标规格一致；未发现规格偏差。

# Known limitations and risks

- Codex 用量接口属于 ChatGPT 后端接口；接口不可用时按规格保留上次成功值或隐藏初始空状态。
- 状态顺序依赖 Pi 默认状态栏按状态键排序的公开当前行为；键 `mcp-codex` 位于 `mcp` 与 `pi-permission-system` 之间。

# Conclusion

通过。实现可以归档。

# Acceptance evidence

<!-- comet-native:acceptance-evidence:start -->
[
  {
    "acceptance_id": "acceptance-170a12b4725ba1b6f6fa4e568bb87c811895aa7da03ccdd0695e8e19700c63bc",
    "evidence_refs": [
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-38fc12d1de0cfc0dd3d802fb90fe6f11360f06ec42933652fff77ad9c26b3fde",
    "evidence_refs": [
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-61dc0765cb1bf0a0909493747601d6b649f777ad0d2a71ba776edc423f72ceb3",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-672adac77ec33b2ac0b2b53d51636ead21ba87ec3739ba2043a961cae5a39161",
    "evidence_refs": [
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-994476761ceb3d21a835fd4486f5a8e3d682045ae9e6370b00398b7889d4eaf2",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-9ad8195f1a6b76283aa1bb073fd6de41b7d438bb4fc812cbf658aab629ab970c",
    "evidence_refs": [
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-a037da605587164884d181e4a308fc31e79570b761b521eb88171298ba6304d5",
    "evidence_refs": [
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-ad0ee5e925a3646ba0bcfcd016dbb52fcd83d8bed831eb90a2f7fcf4d8846d19",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/test_pi_codex_usage_status.py"
    ]
  },
  {
    "acceptance_id": "acceptance-b71848d49cb950e4c227072ba2b776bb23401950aba703d3053bda13d87eb23c",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/test_pi_codex_usage_status.py"
    ]
  },
  {
    "acceptance_id": "acceptance-bc364104e37b87411df164de51c86e7d064cd86c0e360f97f1495b47a5463a1a",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-c2d551ced6587e2334597de6ed56f02a10dd0ced85fc5b16f72729a3b5938048",
    "evidence_refs": [
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-cb002ad794970be71922d042d4a7d38af8e175b5016a5cec36d272c518498b88",
    "evidence_refs": [
      "tests/pi_codex_usage_status.test.mjs"
    ]
  },
  {
    "acceptance_id": "acceptance-e88bbdcd7c6979c08d1872c4bb61ad0510a1e601dea1dda45ea8ea4e15d68529",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts"
    ]
  },
  {
    "acceptance_id": "acceptance-fba23807f6169a4fdaaa0bb104351af428ae3b3c8448f856480af601afaff8bd",
    "evidence_refs": [
      "plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts",
      "tests/test_pi_codex_usage_status.py"
    ]
  }
]
<!-- comet-native:acceptance-evidence:end -->
