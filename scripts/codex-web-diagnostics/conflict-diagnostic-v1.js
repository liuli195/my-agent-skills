// Diagnostic-only addition for codex-chatgpt-web 6.1.2 (Windows x64).
function codexWebConflictDiagnostic(reason, observed, committed, context) {
  const error = new je("ChatGPT changed a completed text block that was already streamed to Codex", {
    reason,
    observedStart: observed.sourceStart,
    observedEnd: observed.sourceEnd,
    committedStart: committed.sourceStart,
    committedEnd: committed.sourceEnd,
    observedTextChars: observed.text.length,
    committedTextChars: committed.text.length,
  });
  try {
    const crypto = require("node:crypto");
    // A fresh, unrecorded key prevents dictionary lookup of short private text.
    // Fingerprints can only be compared within this one conflict record.
    const salt = crypto.randomBytes(32);
    const fingerprint = value => value === undefined ? null : crypto
      .createHmac("sha256", salt).update(JSON.stringify(value)).digest("hex");
    const describe = (block, index) => ({
      index,
      keyFingerprint: fingerprint(block.key),
      tag: /^[a-z][a-z0-9-]{0,40}$/.test(block.tag ?? "") ? block.tag : null,
      textChars: block.text.length,
      textFingerprint: fingerprint(block.text),
      linksFingerprint: fingerprint(block.linkTargets ?? []),
      sourceStart: block.sourceStart,
      sourceEnd: block.sourceEnd,
    });
    const nearby = (blocks, index) => blocks.slice(Math.max(0, index - 2), index + 3)
      .map((block, offset) => describe(block, Math.max(0, index - 2) + offset));
    const observedIndex = context.observed.indexOf(observed);
    const committedIndex = this.committed.indexOf(committed);
    const directMatch = this.committed.findIndex(block =>
      observed.sourceStart !== undefined && block.sourceStart !== undefined
        ? observed.sourceStart === block.sourceStart && observed.tag === block.tag
        : observed.key === block.key);
    error.diagnostic.detail = {
      schemaVersion: 1,
      observedIndex,
      committedIndex,
      previousCommittedIndex: context.previousCommittedIndex,
      pendingBeforeConflict: context.pending.length,
      matchedBy: directMatch >= 0
        ? (observed.sourceStart !== undefined && this.committed[directMatch].sourceStart !== undefined
          ? "source_start_and_tag" : "key")
        : (reason === "source_range_overlap" ? "source_range_overlap" : "unique_tag_and_text"),
      sameText: observed.text === committed.text,
      sameKey: observed.key === committed.key,
      observedCount: context.observed.length,
      committedCount: this.committed.length,
      observed: nearby(context.observed, observedIndex),
      committed: nearby(this.committed, committedIndex),
      pending: context.pending.slice(-3).map((block, index) =>
        describe(block, context.pending.length - Math.min(3, context.pending.length) + index)),
    };
  } catch {
    // Diagnosis must not replace the original exception, even if hashing fails.
    error.diagnostic.detailCaptureFailed = true;
  }
  return error;
}
