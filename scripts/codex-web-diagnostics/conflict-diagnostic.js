// Diagnostic-only addition for codex-chatgpt-web 6.1.2 (Windows x64).
const codexWebReconciliations = new WeakMap();
const codexWebReconciliationPages = new WeakMap();
function codexWebBindReconciliation(stream, page) {
  try { codexWebReconciliationPages.set(stream, page); } catch {}
  return stream;
}
function codexWebPersistReconciliation(stream, diagnostic) {
  let temporary;
  try {
    const journal = codexWebPageJournals.get(codexWebReconciliationPages.get(stream));
    if (!journal) return;
    const fs = require("node:fs"), path = require("node:path");
    const target = path.join(journal.directory, "reconciliation-live.json");
    temporary = target + ".tmp";
    fs.mkdirSync(journal.directory, { recursive: true, mode: 0o700 });
    fs.writeFileSync(temporary, JSON.stringify({ traceId: journal.traceId,
      capturedAt: new Date().toISOString(), markdownConflict: diagnostic }), { mode: 0o600 });
    fs.renameSync(temporary, target);
    temporary = undefined;
  } catch {
    diagnostic.reconciliation.persistFailed = true;
    try { console.warn("[codex-web-diagnostics] reconciliation snapshot write failed"); } catch {}
  } finally {
    if (temporary) { try { require("node:fs").unlinkSync(temporary); } catch {} }
  }
}
function codexWebEncodeReconciliation(raw, salt) {
  const crypto = require("node:crypto");
  const fingerprint = value => value === undefined ? undefined : crypto
    .createHmac("sha256", salt).update(JSON.stringify(value)).digest("hex");
  const encode = blocks => blocks.slice(0, 2000).map(block => {
    const token = fingerprint(block.text);
    // Preserve equality and trim() behavior without retaining even short text.
    const text = block.text.trim() ? token : [...token].map(char =>
      parseInt(char, 16).toString(2).padStart(4, "0").replaceAll("0", " ").replaceAll("1", "\t")).join("");
    return { key: fingerprint(block.key), tag: fingerprint(block.tag), text,
      textChars: block.text.length, tagName: /^[a-z][a-z0-9-]{0,40}$/.test(block.tag ?? "") ? block.tag : null,
      linkTargets: (block.linkTargets ?? []).slice(0, 2000).map(fingerprint),
      linksTruncated: (block.linkTargets?.length ?? 0) > 2000,
      sourceStart: block.sourceStart, sourceEnd: block.sourceEnd };
  });
  const selected = new Set();
  const decisions = raw.decisions.map(event => {
    const blocks = event.kind === "pending" ? raw.latest : raw.committed;
    const direct = [], sameText = [];
    for (let index = 0; index < blocks.length; index++) {
      const old = blocks[index], block = event.block;
      if (block.sourceStart !== undefined && old.sourceStart !== undefined
        ? block.sourceStart === old.sourceStart && block.tag === old.tag : block.key === old.key) direct.push(index);
      if (block.tag === old.tag && block.text === old.text) sameText.push(index);
    }
    const alreadySelected = event.kind === "committed" && event.chosen !== undefined && selected.has(event.chosen);
    if (event.kind === "committed" && event.chosen !== undefined) selected.add(event.chosen);
    return { kind: event.kind, observedIndex: event.observedIndex, chosen: event.chosen ?? null,
      directCandidates: direct.slice(0, 100), directCount: direct.length,
      textCandidates: sameText.slice(0, 100), textCount: sameText.length,
      candidatesTruncated: direct.length > 100 || sameText.length > 100,
      matchedBy: event.chosen === undefined || (event.kind === "pending" && !event.chosen)
        ? "none" : direct.length ? "identity" : "text_fallback", alreadySelected };
  });
  const snapshot = { sequence: raw.sequence, capturedAt: raw.capturedAt,
    counts: { observed: raw.observed.length, committed: raw.committed.length, latest: raw.latest.length },
    observed: encode(raw.observed), committed: encode(raw.committed), latest: encode(raw.latest),
    decisions, decisionsTruncated: raw.decisionsTruncated, observedIndex: raw.observedIndex };
  snapshot.replayable = Object.entries(snapshot.counts).every(([key, count]) =>
    snapshot[key].length === count && snapshot[key].every(block => !block.linksTruncated));
  return snapshot;
}
function codexWebReconcile(stream, observed, run) {
  let state, active;
  try {
    state = codexWebReconciliations.get(stream);
    if (!state) {
      state = { salt: require("node:crypto").randomBytes(32), sequence: 0 };
      codexWebReconciliations.set(stream, state);
    }
    active = { sequence: ++state.sequence, capturedAt: new Date().toISOString(),
      observed: observed.slice(), committed: stream.committed.slice(), latest: stream.latest.slice(),
      decisions: [], decisionsTruncated: false, observedIndex: -1 };
    state.active = active;
  } catch { if (state) state.active = undefined; }
  // Execute the unmodified upstream algorithm exactly once, even if recording fails.
  const result = run();
  try {
    if (result instanceof je) {
      const snapshot = active ? codexWebEncodeReconciliation(active, state.salt) : null;
      state.lastConsistent ??= state.lastConsistentRaw
        ? codexWebEncodeReconciliation(state.lastConsistentRaw, state.salt) : null;
      state.firstConflict ??= snapshot;
      result.diagnostic ??= {};
      result.diagnostic.reconciliation = { schemaVersion: 1,
        captureFailed: !snapshot, lastConsistent: state.lastConsistent ?? null,
        firstConflict: state.firstConflict ?? null, finalConflict: snapshot ?? null };
      codexWebPersistReconciliation(stream, result.diagnostic);
    } else if (active) state.lastConsistentRaw = active;
  } catch {
    if (result instanceof je) { result.diagnostic ??= {}; result.diagnostic.detailCaptureFailed = true; }
  } finally { if (state) state.active = undefined; }
  return result;
}
function codexWebMatchDecision(stream, block, chosen, pending = false) {
  try {
    const snapshot = codexWebReconciliations.get(stream)?.active;
    if (!snapshot) return chosen;
    if (snapshot.decisions.length >= 4000) { snapshot.decisionsTruncated = true; return chosen; }
    if (!pending) snapshot.observedIndex += 1;
    snapshot.decisions.push({ kind: pending ? "pending" : "committed",
      observedIndex: snapshot.observedIndex, block, chosen });
  } catch {}
  return chosen;
}

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
      group: Number.isSafeInteger(block.group) ? block.group : null,
    });
    const nearby = (blocks, index) => blocks.slice(Math.max(0, index - 2), index + 3)
      .map((block, offset) => describe(block, Math.max(0, index - 2) + offset));
    const observedIndex = context.observed.indexOf(observed);
    const committedIndex = this.committed.indexOf(committed);
    const directMatch = this.committed.findIndex(block =>
      observed.sourceStart !== undefined && block.sourceStart !== undefined
        ? observed.sourceStart === block.sourceStart && observed.tag === block.tag
        : observed.key === block.key);
    const linkShape = value => {
      if (typeof value !== "string") return { kind: typeof value };
      try {
        const url = new (require("node:url").URL)(value, "https://diagnostic.invalid/");
        return { kind: /^[a-z][a-z0-9+.-]*:/i.test(value) ? "absolute" : "relative",
          scheme: url.protocol, host: url.host, path: url.pathname,
          query: url.search, queryNames: [...url.searchParams.keys()], fragment: url.hash,
          chars: value.length };
      } catch { return { kind: "unparseable", chars: value.length }; }
    };
    const oldLinks = committed.linkTargets ?? [], newLinks = observed.linkTargets ?? [];
    const linkChanges = Array.from({ length: Math.min(Math.max(oldLinks.length, newLinks.length), 12) }, (_, index) => {
      const before = linkShape(oldLinks[index]), after = linkShape(newLinks[index]);
      return { index, beforeKind: before.kind, afterKind: after.kind,
        beforeChars: before.chars ?? null, afterChars: after.chars ?? null,
        schemeChanged: before.scheme !== after.scheme, hostChanged: before.host !== after.host,
        pathChanged: before.path !== after.path, queryChanged: before.query !== after.query,
        queryNamesChanged: JSON.stringify(before.queryNames) !== JSON.stringify(after.queryNames),
        fragmentChanged: before.fragment !== after.fragment };
    });
    error.diagnostic.detail = {
      schemaVersion: 3,
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
      sameTag: observed.tag === committed.tag,
      candidateCounts: {
        sameKey: this.committed.filter(block => block.key === observed.key).length,
        sameTagAndText: this.committed.filter(block =>
          block.tag === observed.tag && block.text === observed.text).length,
        sameSourceStartAndTag: this.committed.filter(block =>
          block.sourceStart !== undefined && block.sourceStart === observed.sourceStart
            && block.tag === observed.tag).length,
      },
      linkCounts: { committed: oldLinks.length, observed: newLinks.length,
        compared: linkChanges.length, truncated: Math.max(oldLinks.length, newLinks.length) > linkChanges.length },
      linkChanges,
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

// Independent of page reads and terminal checkpoints. Atomic snapshots survive a
// killed helper; they do not promise durability across an OS crash/power loss.
const codexWebJournals = new Map();
const codexWebPageJournals = new WeakMap();
function codexWebDiagnosticKind(error) {
  if (error?.name === "AbortError") return "aborted";
  if (error?.name === "ChatGptBrowserObservationTimeoutError") return "dom_timeout";
  if (/browser stage timed out/.test(error?.message ?? "")) return "stage_timeout";
  if (/closed|disconnected/i.test(error?.message ?? "")) return "connection_closed";
  return "other";
}
function codexWebJournalWrite(journal, phase, detail = {}) {
  if (!journal || journal.finished) return;
  let temporary;
  try {
    const fs = require("node:fs"), path = require("node:path");
    const event = { phase, elapsedMs: Math.round(performance.now() - journal.started), ...detail };
    // Keep turn lifecycle evidence separate from the high-frequency send ring.
    if (phase !== "send_progress") {
      journal.events.push(event);
      if (journal.events.length > 40) journal.events.shift();
    }
    journal.sequence += 1;
    const send = journal.page ? codexWebSendCapture(journal.page) : undefined;
    const filename = phase === "send_progress" ? `send-${journal.sendNumber}-live.json` : "turn-live.json";
    const target = path.join(journal.directory, filename);
    temporary = target + ".tmp";
    fs.mkdirSync(journal.directory, { recursive: true, mode: 0o700 });
    fs.writeFileSync(temporary, JSON.stringify({ schemaVersion: 4, traceId: journal.traceId,
      pid: process.pid, capturedAt: new Date().toISOString(), sequence: journal.sequence,
      writeFailures: journal.writeFailures, phase, events: journal.events,
      sendNumber: journal.sendNumber, sendDiagnostic: send }), { mode: 0o600 });
    fs.renameSync(temporary, target);
    temporary = undefined;
  } catch {
    journal.writeFailures += 1;
    if (journal.writeFailures === 1) {
      try { console.warn("[codex-web-diagnostics] live snapshot write failed; original operation continues"); } catch {}
    }
  } finally {
    if (temporary) { try { require("node:fs").unlinkSync(temporary); } catch {} }
  }
}
function codexWebJournalTrace(traceId, phase, detail = {}) {
  try { codexWebJournalWrite(codexWebJournals.get(traceId), phase, detail); } catch {}
}
function codexWebJournalAll(phase) {
  for (const journal of codexWebJournals.values()) codexWebJournalWrite(journal, phase);
}
function codexWebJournalExit() { codexWebJournalAll("process_exit"); }
function codexWebJournalOpen(capture, signal) {
  try {
    const journal = { traceId: capture.traceId, directory: capture.directory,
      started: performance.now(), sequence: 0, sendNumber: 0, writeFailures: 0,
      events: [], cleanup: [], pages: new WeakSet() };
    if (codexWebJournals.size === 0) process.on("exit", codexWebJournalExit);
    codexWebJournals.set(capture.traceId, journal);
    const abort = () => codexWebJournalWrite(journal, "turn_abort", { kind: codexWebDiagnosticKind(signal?.reason) });
    signal?.addEventListener("abort", abort, { once: true });
    journal.cleanup.push(() => signal?.removeEventListener("abort", abort));
    codexWebJournalWrite(journal, "turn_started");
    if (signal?.aborted) abort();
  } catch { /* Diagnosis must not affect turn setup. */ }
}
function codexWebJournalBind(capture, page) {
  try {
    const journal = codexWebJournals.get(capture.traceId);
    if (!journal || !page) return;
    codexWebPageJournals.set(page, journal);
    journal.page = page;
    if (journal.pages.has(page)) return;
    journal.pages.add(page);
    for (const event of ["close", "crash"]) {
      const listener = () => codexWebJournalWrite(journal, `page_${event}`);
      page.on?.(event, listener);
      journal.cleanup.push(() => page.off?.(event, listener));
    }
    const browser = page.context?.().browser?.();
    if (browser && browser !== journal.browser) {
      journal.browser = browser;
      const listener = () => codexWebJournalWrite(journal, "browser_disconnected");
      browser.on("disconnected", listener);
      journal.cleanup.push(() => browser.off("disconnected", listener));
    }
    codexWebJournalWrite(journal, "page_bound");
  } catch { /* Diagnosis must not affect page binding. */ }
}
function codexWebJournalClose(capture) {
  try {
    const journal = codexWebJournals.get(capture.traceId);
    if (!journal) return;
    codexWebJournalWrite(journal, "turn_finally");
    journal.finished = true;
    for (const dispose of journal.cleanup) { try { dispose(); } catch {} }
    codexWebJournals.delete(capture.traceId);
    if (codexWebJournals.size === 0) process.off("exit", codexWebJournalExit);
  } catch {}
}

// One bounded record per active page. No prompt text, URLs, node ids or tool arguments.
const codexWebSendRecords = new WeakMap();
function codexWebSendRecord(page, phase, detail = {}) {
  try {
    const record = codexWebSendRecords.get(page);
    if (!record) return;
    const event = { phase, elapsedMs: Math.round(performance.now() - record.started), ...detail };
    if (["send_ready", "activation_started", "activation_completed", "activation_failed",
      "press_started", "press_completed", "press_failed", "submission_failed",
      "submission_confirmed", "dom_rebind_attempt", "dom_rebound",
      "tool_evidence", "dom_evidence"].includes(phase)
      || /^(ready_capture|dom_read|session_check|rate_limit_check|button_session_check|button_rate_limit_check|button_enabled_check|button_visible|active_composer|tool_answer_observation|tool_batch_ack|submission_race|external_wait)_(started|completed|failed)$/.test(phase)) {
      const milestone = record.milestones[phase] ??= { firstElapsedMs: event.elapsedMs, count: 0 };
      milestone.lastElapsedMs = event.elapsedMs;
      milestone.count += 1;
    }
    record.eventCount += 1;
    record.events.push(event);
    if (record.events.length > 40) record.events.shift();
    const now = performance.now();
    const frequent = /^(button_enabled_check|button_session_check|button_rate_limit_check)_(started|completed)$/.test(phase);
    if (!frequent || detail.enabled === true || phase.endsWith("failed")
      || record.lastButtonWrite === undefined || now - record.lastButtonWrite >= 1000) {
      if (frequent) record.lastButtonWrite = now;
      codexWebJournalWrite(codexWebPageJournals.get(page), "send_progress");
    }
  } catch { /* Evidence must never change the send result. */ }
}
async function codexWebSendStep(page, phase, run) {
  const started = performance.now();
  codexWebSendRecord(page, `${phase}_started`);
  try {
    const value = await run();
    codexWebSendRecord(page, `${phase}_completed`, {
      durationMs: Math.round(performance.now() - started),
    });
    return value;
  } catch (error) {
    codexWebSendRecord(page, `${phase}_failed`, {
      durationMs: Math.round(performance.now() - started),
      kind: error?.name === "AbortError" ? "aborted" : "other",
    });
    throw error;
  }
}
async function codexWebSendButtonCheck(page, run) {
  const started = performance.now();
  codexWebSendRecord(page, "button_enabled_check_started");
  try {
    const enabled = await run();
    codexWebSendRecord(page, "button_enabled_check_completed", {
      enabled: Boolean(enabled), durationMs: Math.round(performance.now() - started),
    });
    return enabled;
  } catch (error) {
    codexWebSendRecord(page, "button_enabled_check_failed", {
      kind: codexWebDiagnosticKind(error), durationMs: Math.round(performance.now() - started),
    });
    throw error;
  }
}
function codexWebSendStart(page, prompt) {
  try {
    codexWebCompletionRecords.delete(page);
    codexWebCompletionKeys.delete(page);
    const record = {
      schemaVersion: 4, started: performance.now(), events: [], eventCount: 0,
      milestones: {}, promptChars: prompt?.length ?? 0,
      promptFingerprint: null, diagnosticFailureKind: null,
    };
    codexWebSendRecords.set(page, record);
    const journal = codexWebPageJournals.get(page);
    if (journal) { journal.page = page; journal.sendNumber += 1; }
    try {
      const crypto = require("node:crypto");
      record.promptFingerprint = crypto.createHmac("sha256", crypto.randomBytes(32))
        .update(prompt ?? "").digest("hex");
    } catch { record.diagnosticFailureKind = "fingerprint_failed"; }
    codexWebSendRecord(page, "send_ready");
  } catch { /* Evidence must never change the send result. */ }
}
function codexWebSendProgress(page, snapshot) {
  try {
    const record = codexWebSendRecords.get(page);
    if (!record || !snapshot) return;
    const revision = snapshot.revision ?? null;
    const toolRevision = snapshot.lastToolBatchRevision ?? null;
    if (record.lastRevision === revision && record.lastToolRevision === toolRevision) return;
    record.lastRevision = revision;
    record.lastToolRevision = toolRevision;
    codexWebSendRecord(page, "external_progress", { revision, toolRevision });
  } catch { /* Evidence must never change the send result. */ }
}
function codexWebSendMove(oldPage, newPage) {
  try {
    const record = codexWebSendRecords.get(oldPage);
    if (record && newPage !== oldPage) codexWebSendRecords.set(newPage, record);
    const journal = codexWebPageJournals.get(oldPage);
    if (journal) codexWebJournalBind(journal, newPage);
    codexWebSendRecord(newPage, "dom_rebound");
  } catch { /* Evidence must never change the send result. */ }
}
async function codexWebObserveSubmission(page, read) {
  const record = codexWebSendRecords.get(page);
  if (!record) return read();
  const started = performance.now();
  codexWebSendRecord(page, "dom_read_started");
  try {
    const result = await read();
    const snapshot = result?.snapshot;
    codexWebSendRecord(page, "dom_read_completed", {
      durationMs: Math.round(performance.now() - started),
      userTurns: snapshot?.userTurnCount ?? null,
      assistantTurns: snapshot?.assistantTurnCount ?? null,
      visibleStopButtons: snapshot?.visibleStopButtonCount ?? null,
      composerChars: snapshot?.composerChars ?? null,
      cacheHit: !snapshot,
    });
    return result;
  } catch (error) {
    codexWebSendRecord(page, "dom_read_failed", {
      durationMs: Math.round(performance.now() - started),
      kind: error?.name === "ChatGptBrowserObservationTimeoutError" ? "timeout"
        : error?.name === "AbortError" ? "aborted" : "other",
    });
    throw error;
  }
}
function codexWebSendCapture(page) {
  try {
    const record = codexWebSendRecords.get(page);
    return record ? {
      schemaVersion: record.schemaVersion, promptChars: record.promptChars,
      promptFingerprint: record.promptFingerprint,
      diagnosticFailureKind: record.diagnosticFailureKind, eventCount: record.eventCount,
      milestones: JSON.parse(JSON.stringify(record.milestones)), events: record.events.slice(),
    } : undefined;
  } catch { return undefined; }
}

const codexWebCompletionRecords = new WeakMap();
const codexWebCompletionKeys = new WeakMap();
function codexWebStoreCompletion(page, serialized) {
  try {
    const source = JSON.parse(serialized);
    let fingerprintFailed = false;
    if (typeof source.response?.rawAnswer === "string") {
      try {
        let key = codexWebCompletionKeys.get(page);
        if (!key) {
          key = require("node:crypto").randomBytes(32);
          codexWebCompletionKeys.set(page, key);
        }
        source.response.answerFingerprint = require("node:crypto")
          .createHmac("sha256", key).update(source.response.rawAnswer).digest("hex");
      } catch {
        fingerprintFailed = true;
      } finally {
        delete source.response.rawAnswer;
      }
    }
    const knownTokens = new Set(["div", "span", "button", "input", "a", "p", "section",
      "button", "status", "dialog", "alert", "textbox", "true", "false", "submit",
      "data-testid", "aria-label", "aria-disabled", "aria-hidden", "role", "type",
      "class", "title", "copy-turn-action-button", "turn-action-controls"]);
    const safeToken = value => typeof value === "string"
      ? value.startsWith("conversation-turn-") ? "conversation-turn-*"
        : knownTokens.has(value) ? value : null : null;
    const knownLabels = new Set(["Copy", "Copy link", "Retry", "Regenerate", "Share",
      "Edit", "Delete", "复制", "复制链接", "重试", "重新生成", "分享", "编辑", "删除"]);
    const safeUiLabel = (value, isUiButton) => isUiButton && knownLabels.has(value) ? value : null;
    const labelFingerprint = value => {
      if (typeof value !== "string") return null;
      let key = codexWebCompletionKeys.get(page);
      if (!key) { key = require("node:crypto").randomBytes(32); codexWebCompletionKeys.set(page, key); }
      return require("node:crypto").createHmac("sha256", key).update(value).digest("hex");
    };
    const safeAncestor = value => ({
      tag: safeToken(value.tag), role: safeToken(value.role),
      testId: safeToken(value.testId), classes: (value.classes ?? []).slice(0, 20).map(safeToken),
      classCount: value.classCount ?? 0, classesTruncated: Boolean(value.classesTruncated),
    });
    const safeControl = value => ({
      tag: safeToken(value.tag), role: safeToken(value.role), testId: safeToken(value.testId),
      type: safeToken(value.type), classes: (value.classes ?? []).slice(0, 20).map(safeToken),
      classCount: value.classCount ?? 0, classesTruncated: Boolean(value.classesTruncated),
      ancestors: (value.ancestors ?? []).slice(0, 5).map(safeAncestor),
      attributeNames: (value.attributeNames ?? []).slice(0, 20).map(safeToken),
      withinCurrent: Boolean(value.withinCurrent), withinAssistant: Boolean(value.withinAssistant),
      nearCurrent: Boolean(value.nearCurrent),
      visible: Boolean(value.visible), disabled: Boolean(value.disabled),
      ariaDisabled: value.ariaDisabled === "true", ariaHidden: value.ariaHidden === "true",
      uiAction: Boolean(value.uiAction),
      ariaLabel: safeUiLabel(value.ariaLabel, value.uiAction && value.tag === "button"),
      title: safeUiLabel(value.title, value.uiAction && value.tag === "button"),
      ariaLabelFingerprint: labelFingerprint(value.ariaLabel),
      titleFingerprint: labelFingerprint(value.title),
      selectorHits: value.selectorHits ? {
        configured: Boolean(value.selectorHits.configured),
        copyAction: Boolean(value.selectorHits.copyAction),
        actionContainer: Boolean(value.selectorHits.actionContainer),
      } : undefined,
      ariaLabelChars: value.ariaLabelChars ?? 0, titleChars: value.titleChars ?? 0,
      textChars: value.textChars ?? 0,
    });
    const previous = codexWebCompletionRecords.get(page) ?? {};
    codexWebCompletionRecords.set(page, {
      schemaVersion: 3,
      answerChars: source.response?.textChars ?? previous.answerChars ?? 0,
      visibleAnswerChars: source.response?.visibleTextChars ?? previous.visibleAnswerChars ?? null,
      answerHtmlChars: source.response?.htmlChars ?? previous.answerHtmlChars ?? 0,
      answerFingerprint: source.response?.answerFingerprint ?? previous.answerFingerprint ?? null,
      lastMutationAt: source.response?.lastMutationAt ?? previous.lastMutationAt ?? null,
      globalActions: source.globalActions ?? previous.globalActions ?? null,
      currentActions: source.response?.matchedActionCount ?? previous.currentActions ?? null,
      currentTurnOrdinal: source.currentTurnOrdinal ?? previous.currentTurnOrdinal ?? null,
      targetTurnOrdinal: source.response?.targetTurnOrdinal ?? previous.targetTurnOrdinal ?? null,
      targetIsLastAssistant: source.response?.targetIsLastAssistant ?? previous.targetIsLastAssistant ?? null,
      targetCandidateCounts: source.response?.targetCandidateCounts
        ?? previous.targetCandidateCounts ?? null,
      perAssistantActionCounts: source.perAssistantActionCounts ?? previous.perAssistantActionCounts ?? [],
      candidateCounts: source.candidateCounts ?? previous.candidateCounts ?? null,
      diagnosticFailureKind: fingerprintFailed ? "fingerprint_failed" : source.diagnosticError
        ? (source.diagnosticError.includes("timed out") ? "timeout" : "other")
        : previous.diagnosticFailureKind ?? null,
      nearbyControls: source.response?.descriptors
        ? source.response.descriptors.slice(-80).map(safeControl) : previous.nearbyControls ?? [],
      targetControls: source.response?.targetTurnOrdinal !== undefined
        ? (source.response.descriptors ?? []).slice(-80).map(safeControl)
        : previous.targetControls ?? [],
      surroundingControls: source.response?.surroundingControls
        ? source.response.surroundingControls.slice(-80).map(safeControl) : previous.surroundingControls ?? [],
      globalMatchedControls: source.globalMatchedControls
        ? source.globalMatchedControls.slice(-80).map(safeControl) : previous.globalMatchedControls ?? [],
      globalFallbackControls: source.globalFallbackControls
        ? source.globalFallbackControls.slice(-80).map(safeControl) : previous.globalFallbackControls ?? [],
      overlays: source.overlays
        ? source.overlays.slice(-30).map(safeControl) : previous.overlays ?? [],
    });
  } catch {
    // Preserve an explicit gap when the diagnostic itself fails.
    try {
      codexWebCompletionRecords.set(page, {
        ...(codexWebCompletionRecords.get(page) ?? {}), schemaVersion: 3,
        diagnosticFailureKind: "capture_failed",
      });
    } catch { /* Diagnostic evidence must never change completion behavior. */ }
  }
}
function codexWebCompletionCapture(page) {
  return codexWebCompletionRecords.get(page);
}
