# 02 — Clean up Claude Legacy MySpec Plugin

## Parent

GitHub issue #252

**What to build:** Make Claude initialization uninstall the exact legacy MySpec plugin after the independent plugin is verified, while preserving persistent data, the shared marketplace, and unrelated plugins.

**Blocked by:** None — can start immediately.

**Status:** implemented

- [x] Packed `myspec init --claude` uninstalls only the exact legacy plugin with persistent-data preservation.
- [x] The shared marketplace, unrelated plugins, and persistent user data remain unchanged.
- [x] An already-clean state succeeds without an uninstall call and reports an empty removal result.
- [x] A failed or incomplete detected uninstall returns nonzero and a retry can converge.
- [x] doctor（诊断）does not report a Legacy MySpec Source when only the shared marketplace remains.
- [x] Packed CLI verification covers observable plugin state, command calls, result fields, and doctor output.

## Evidence

- Red: Build and Verify（构建与验证）`verify.my-spec` failed because initialization still returned `disabledLegacyPlugins` and retained the legacy plugin.
- Green: the same fast verification passed with 85 tests passed and 2 skipped in `verify.my-spec`.
- User-entry smoke: a packed candidate and the real Claude（代码代理）client ran in an isolated HOME（用户目录）; `init --claude` removed the seeded legacy plugin, preserved its persistent data, and `doctor --claude` reported only the stable source.
- Review: pending.
- Unresolved risk: none.
