# 03 — Clean up Codex Legacy MySpec Plugin

## Parent

GitHub issue #252

**What to build:** Make Codex initialization remove the exact legacy MySpec plugin record and cache after the independent plugin is verified, while preserving the shared marketplace and unrelated plugins.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Packed `myspec init --codex` removes only the exact legacy plugin through the Codex command interface.
- [ ] The shared marketplace, unrelated plugins, and unrelated cache remain unchanged.
- [ ] An already-clean state succeeds without a removal call and reports an empty removal result.
- [ ] A failed or incomplete detected removal returns nonzero and a retry can converge.
- [ ] doctor（诊断）does not report a Legacy MySpec Source when only the shared marketplace remains.
- [ ] Packed CLI verification covers observable plugin state, command calls, result fields, and doctor output.
