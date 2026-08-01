# 01 — Clean up Pi Legacy MySpec Sources

## Parent

GitHub issue #252

**What to build:** Make Pi initialization remove each user-level Legacy MySpec Source（旧 MySpec 来源）after the independent source is verified, while retaining and disabling project-level legacy sources.

**Blocked by:** None — can start immediately.

**Status:** implemented

- [x] Packed `myspec init --pi` removes only detected user-level legacy sources through the Pi command interface.
- [x] Project-level legacy sources remain in project settings and are disabled.
- [x] Unrelated packages and the independent MySpec source remain unchanged and enabled.
- [x] An already-clean state succeeds without a removal call and reports empty removal results.
- [x] A failed or incomplete detected removal returns nonzero and a retry can converge.
- [x] Packed CLI verification covers observable settings, command calls, result fields, and doctor output.

## Evidence

- Red: Build and Verify（构建与验证）`verify.my-spec` failed because initialization still returned `disabledLegacySources` and retained the user legacy source.
- Green: the same fast verification passed after the review fixes with 82 tests passed and 2 skipped in `verify.my-spec`.
- User-entry smoke: a packed candidate ran against the real Pi（编码代理）client in an isolated HOME（用户目录）; `init --pi` removed the seeded legacy source and `doctor --pi` reported one enabled source, no disabled source, and no duplicate.
- Review: initial Standards（规范）and Spec（规格）review found that cleanup preceded stable-source verification and that failure/no-op command evidence was incomplete; both findings were fixed and covered through the packed CLI seam. Targeted follow-up pending.
- Unresolved risk: none.
