# 01 — Clean up Pi Legacy MySpec Sources

## Parent

GitHub issue #252

**What to build:** Make Pi initialization remove each user-level Legacy MySpec Source（旧 MySpec 来源）after the independent source is verified, while retaining and disabling project-level legacy sources.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Packed `myspec init --pi` removes only detected user-level legacy sources through the Pi command interface.
- [ ] Project-level legacy sources remain in project settings and are disabled.
- [ ] Unrelated packages and the independent MySpec source remain unchanged and enabled.
- [ ] An already-clean state succeeds without a removal call and reports empty removal results.
- [ ] A failed or incomplete detected removal returns nonzero and a retry can converge.
- [ ] Packed CLI verification covers observable settings, command calls, result fields, and doctor output.
