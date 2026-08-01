# 02 — Clean up Claude Legacy MySpec Plugin

## Parent

GitHub issue #252

**What to build:** Make Claude initialization uninstall the exact legacy MySpec plugin after the independent plugin is verified, while preserving persistent data, the shared marketplace, and unrelated plugins.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Packed `myspec init --claude` uninstalls only the exact legacy plugin with persistent-data preservation.
- [ ] The shared marketplace, unrelated plugins, and persistent user data remain unchanged.
- [ ] An already-clean state succeeds without an uninstall call and reports an empty removal result.
- [ ] A failed or incomplete detected uninstall returns nonzero and a retry can converge.
- [ ] doctor（诊断）does not report a Legacy MySpec Source when only the shared marketplace remains.
- [ ] Packed CLI verification covers observable plugin state, command calls, result fields, and doctor output.
