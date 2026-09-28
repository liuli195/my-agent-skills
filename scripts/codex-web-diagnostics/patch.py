"""Apply/revert a diagnostic-only patch to a verified 6.1.2 or 6.1.3 helper."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


ORIGINAL_SHA256 = "3d0f23940ce651968a45538fc0afcea2260a8bbafd94f1244515e41085d1a656"
ORIGINAL_MANIFEST_SHA256 = "668249153aa0af541afbc26b4b7930fad296ec61cfd9365f37ee6b76daaf1771"
ORIGINAL_613_SHA256 = "3110a8cd52821ae1a61e5001b8ff91097dc744ec2b13ee17f270a20e5cc25944"
ORIGINAL_613_MANIFEST_SHA256 = "dd20c850a6c2604b61df70488d6359b1d0b8e50023917bc0ec2c9ffd53cbdaf3"
PREVIOUS_PATCH_SHA256 = "9fd465a3b4c957b37890962eaa06520f2092959d3ad0030a3dc1a2368bf3fbb6"
SECOND_PATCH_SHA256 = "d405304507f61ef3e2cd3c65a770159526cb7f65e332a3e3eb2aa72b5f03fbf1"
THIRD_PATCH_SHA256 = "0602eebd0ee1296f880bd733fc552449a35761c41cc40b9676cd2249c182e682"
FOURTH_PATCH_SHA256 = "02fd9d4e79111afd6a7b42f6b7c0ecd389244288890844790a69de00fef1a8cb"
FIFTH_PATCH_SHA256 = "de448563bbda99edc383dab5f1ab21298550fd54911a0b9ba766e806b1e76c96"
PATCH_SOURCE = Path(__file__).with_name("conflict-diagnostic.js")
LEGACY_PATCH_SOURCE = Path(__file__).with_name("conflict-diagnostic-v1.js")
OLD_METHOD = 'changedCommittedBlockError(e,t,r){return new je("ChatGPT changed a completed text block that was already streamed to Codex",{reason:e,observedStart:t.sourceStart,observedEnd:t.sourceEnd,committedStart:r.sourceStart,committedEnd:r.sourceEnd,observedTextChars:t.text.length,committedTextChars:r.text.length})}'
OLD_THROW = 'throw new k(f.message,{status:502,errorType:"server_error",code:"browser_stream_inconsistent",retryable:!1})'
NEW_THROW = '{const diagnosticError=new k(f.message,{status:502,errorType:"server_error",code:"browser_stream_inconsistent",retryable:!1});diagnosticError.diagnostic=f.diagnostic;throw diagnosticError}'
CAPTURE_ANCHOR = 'checkpoint:t,...r!==void 0?{error:ht(r instanceof Error?r.message:String(r))}:{},'
COMPLETION_SHAPE = '''(()=>{
  if (!["response-stalled-60s", "turn-failed", "turn-completed"].includes(diagnosticCheckpoint)) return;
  const current = F.at(-1);
  const currentRect = current?.getBoundingClientRect();
  const shape = node => {
    const part = element => ({tag:element.tagName.toLowerCase(),role:element.getAttribute("role"),
      testId:element.getAttribute("data-testid"),classes:[...element.classList].slice(0,20),
      classCount:element.classList.length,classesTruncated:element.classList.length>20});
    const ancestors = [];
    for (let parent=node.parentElement; parent && ancestors.length<5; parent=parent.parentElement) ancestors.push(part(parent));
    const style = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    const nearCurrent = Boolean(currentRect && Math.abs(rect.top-currentRect.bottom)<800
      && Math.abs(rect.left-currentRect.left)<1000);
    const uiAction = node.tagName==="BUTTON" && (Boolean(node.closest(".turn-action-controls"))
      || node.matches(x) || Boolean(current?.parentElement?.contains(node) && !current.contains(node))
      || Boolean(nearCurrent && !current?.contains(node)));
    return {...part(node),type:node.getAttribute("type"),ancestors,
      attributeNames:[...node.attributes].map(attribute=>attribute.name).slice(0,20),
      withinCurrent:Boolean(current?.contains(node)),withinAssistant:Boolean(node.closest(y)),
      nearCurrent,
      visible:node.isConnected && style.display!=="none" && style.visibility!=="hidden"
        && style.opacity!=="0" && node.getClientRects().length>0,
      disabled:Boolean(node.disabled),ariaDisabled:node.getAttribute("aria-disabled"),
      ariaHidden:node.getAttribute("aria-hidden"),uiAction,
      ariaLabel:uiAction?node.getAttribute("aria-label"):null,
      title:uiAction?node.getAttribute("title"):null,
      selectorHits:{configured:node.matches(x),copyAction:node.matches('button[data-testid="copy-turn-action-button"]'),
        actionContainer:Boolean(node.closest(".turn-action-controls"))},
      ariaLabelChars:(node.getAttribute("aria-label")??"").length,
      titleChars:(node.getAttribute("title")??"").length,textChars:(node.textContent??"").length};
  };
  const candidateNodes = current ? [...current.querySelectorAll('button,[role="button"],[aria-label],[data-testid*="action"],[data-testid*="copy"]')] : [];
  const candidates = candidateNodes.slice(-80);
  const all = [...document.querySelectorAll(x)];
  const surroundingNodes = current?.parentElement
    ? [...current.parentElement.querySelectorAll('button,[role="button"],[aria-label],[data-testid*="action"],[data-testid*="copy"]')]
    : [];
  const surrounding = surroundingNodes.slice(-80);
  const currentMatches = current?.querySelectorAll(x).length??0;
  const globalFallbackNodes = currentMatches===0
    ? [...document.querySelectorAll('button,[role="button"],[aria-label],[data-testid*="action"],[data-testid*="copy"]')]
    : [];
  const globalFallback = currentRect
    ? globalFallbackNodes.map(node=>({node,rect:node.getBoundingClientRect()}))
      .sort((a,b)=>Math.abs(a.rect.top-currentRect.bottom)-Math.abs(b.rect.top-currentRect.bottom))
      .slice(0,80).map(item=>item.node)
    : globalFallbackNodes.slice(-80);
  return {response:{textChars:(current?.textContent??"").length,htmlChars:current?.innerHTML.length??0,
      visibleTextChars:(current?.innerText??"").length,rawAnswer:current?.innerText??"",
      lastMutationAt:globalThis.__CODEX_WEB_GPT_RESPONSE_OBSERVERS__?.states?.get(current)?.lastMutationAt??null,
      matchedActionCount:currentMatches,
      descriptors:candidates.map(shape),surroundingControls:surrounding.map(shape)},
    currentTurnOrdinal:F.length-1,perAssistantActionCounts:F.map(turn=>turn.querySelectorAll(x).length),
    candidateCounts:{currentTotal:candidateNodes.length,currentRetained:candidates.length,
      surroundingTotal:surroundingNodes.length,surroundingRetained:surrounding.length,
      globalMatchedTotal:all.length,globalMatchedRetained:Math.min(all.length,80),
      globalFallbackTotal:globalFallbackNodes.length,globalFallbackRetained:globalFallback.length},
    globalActions:{total:all.length,visible:all.filter(_).length,
      copySelector:document.querySelectorAll('button[data-testid="copy-turn-action-button"]').length,
      actionContainerSelector:document.querySelectorAll('[data-turn-key] .turn-action-controls button').length},
    globalMatchedControls:all.slice(-80).map(shape),
    globalFallbackControls:globalFallback.map(shape),
    overlays:[...document.querySelectorAll('[role="dialog"],[role="alert"],[role="status"]')].filter(_).slice(-20).map(shape)};
})()'''
STALL_CONTROLS_OLD = '''let i=o,a=[...i.querySelectorAll("[role], [data-testid], button, [aria-label]")].filter((s)=>{let c=getComputedStyle(s);return c.visibility!=="hidden"&&c.display!=="none"}).slice(-80).map((s)=>({tag:s.tagName.toLowerCase(),role:s.getAttribute("role"),testId:s.getAttribute("data-testid"),ariaLabelChars:s.getAttribute("aria-label")?.length??0,titleChars:s.getAttribute("title")?.length??0,textChars:(s.innerText??s.textContent??"").trim().length}));'''
STALL_CONTROLS_NEW = '''let i=o,aNodes=[...i.querySelectorAll("[role], [data-testid], button, [aria-label]")],a=aNodes.slice(-80).map((s)=>{
  let part=(node)=>({tag:node.tagName.toLowerCase(),role:node.getAttribute("role"),
    testId:node.getAttribute("data-testid"),classes:[...node.classList].slice(0,20),
    classCount:node.classList.length,classesTruncated:node.classList.length>20}),
    parents=[],style=getComputedStyle(s);
  for(let p=s.parentElement;p&&parents.length<5;p=p.parentElement)parents.push(part(p));
  return {...part(s),type:s.getAttribute("type"),ancestors:parents,
    attributeNames:[...s.attributes].map(attr=>attr.name).slice(0,20),
    withinCurrent:true,withinAssistant:true,uiAction:Boolean(s.closest(".turn-action-controls")),
    visible:s.isConnected&&style.display!=="none"&&style.visibility!=="hidden"
      &&style.opacity!=="0"&&s.getClientRects().length>0,
    disabled:Boolean(s.disabled),ariaDisabled:s.getAttribute("aria-disabled"),
    ariaHidden:s.getAttribute("aria-hidden"),
    selectorHits:{configured:s.matches(selectors.completion),
      copyAction:s.matches('button[data-testid="copy-turn-action-button"]'),
      actionContainer:Boolean(s.closest(".turn-action-controls"))},
    ariaLabelChars:s.getAttribute("aria-label")?.length??0,
    titleChars:s.getAttribute("title")?.length??0,
    textChars:(s.innerText??s.textContent??"").trim().length};
});'''


def replacements(*, legacy: bool = False) -> list[tuple[str, str]]:
    # Read normalized patch text so checkout line endings do not change the patch.
    source = LEGACY_PATCH_SOURCE if legacy else PATCH_SOURCE
    addition = source.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip() + "\n"
    context = '{observed:e,pending:t,previousCommittedIndex:o}'
    edits = [
        ('class je extends Error', addition + 'class je extends Error'),
        (OLD_METHOD, 'changedCommittedBlockError(e,t,r,context){return codexWebConflictDiagnostic.call(this,e,t,r,context)}'),
        ('"text_changed",s,h)', '"text_changed",s,h,' + context + ')'),
        ('("link_target_changed",s,h)', '("link_target_changed",s,h,' + context + ')'),
        ('("source_range_overlap",s,r)', '("source_range_overlap",s,r,' + context + ')'),
        (OLD_THROW, NEW_THROW),
        (CAPTURE_ANCHOR, CAPTURE_ANCHOR + '...r?.diagnostic?.detail||r?.diagnostic?.detailCaptureFailed?{markdownConflict:r.diagnostic}:{},'),
    ]
    if not legacy:
        edits.extend([
            ('async sendAttachedPrompt(e,t,r,n,o,i,a,s){let l=(await this.activeComposer(e)).locator("xpath=ancestor::form[1]").locator(Ar);await l.waitFor({state:"visible",timeout:ee.send}),await we();',
             'async sendAttachedPrompt(e,t,r,n,o,i,a,s){codexWebSendStart(e,t.submittedText);let l=(await codexWebSendStep(e,"active_composer",()=>this.activeComposer(e))).locator("xpath=ancestor::form[1]").locator(Ar);await codexWebSendStep(e,"button_visible",()=>l.waitFor({state:"visible",timeout:ee.send})),await we();'),
            ('if(await Ae(e),await ge(e),await l.isEnabled())break;',
             'if(await codexWebSendStep(e,"button_session_check",()=>Ae(e)),await codexWebSendStep(e,"button_rate_limit_check",()=>ge(e)),await codexWebSendButtonCheck(e,()=>l.isEnabled()))break;'),
            ('if(Date.now()>=h)throw await r?.("send-disabled"),Error("ChatGPT send button remained disabled after the complete prompt was attached");',
             'if(Date.now()>=h)throw codexWebSendRecord(e,"button_disabled_timeout"),await r?.("send-disabled"),Error("ChatGPT send button remained disabled after the complete prompt was attached");'),
            ('P=new Po,O=new ur,S=', 'P=new Po,O=codexWebBindReconciliation(new ur,w),S='),
            ('reconcile(e){if(this.committed.length',
             'reconcile(e){return codexWebReconcile(this,e,()=>this.codexWebOriginalReconcile(e))}codexWebOriginalReconcile(e){if(this.committed.length'),
            ('committedIndex(e){let t=',
             'committedIndex(e){return codexWebMatchDecision(this,e,this.codexWebOriginalCommittedIndex(e))}codexWebOriginalCommittedIndex(e){let t='),
            ('matchesLatestPending(e){if(this.latest',
             'matchesLatestPending(e){return codexWebMatchDecision(this,e,this.codexWebOriginalMatchesLatestPending(e),true)}codexWebOriginalMatchesLatestPending(e){if(this.latest'),
            ('h,p,m,C=[],y=new xo;try{',
             'h,p,m,C=[],y=new xo;codexWebJournalOpen(l,e.abortSignal);try{'),
            ('async capture(e,t,r){try{',
             'async capture(e,t,r){codexWebJournalBind(this,e);codexWebJournalTrace(this.traceId,"checkpoint_started",{checkpoint:t});try{'),
            ('catch(b){if(!(b instanceof DOMException&&b.name==="AbortError")',
             'catch(b){codexWebJournalTrace(e.traceId,"turn_catch",{kind:codexWebDiagnosticKind(b)});if(!(b instanceof DOMException&&b.name==="AbortError")'),
            ('finally{if(y.dispose(),', 'finally{codexWebJournalClose(l);if(y.dispose(),'),
            ('console.info(`[chatgpt-web] browser turn ${e} stage=${t} started`);',
             'codexWebJournalTrace(e,"stage_started",{stage:t,budgetMs:r});console.info(`[chatgpt-web] browser turn ${e} stage=${t} started`);'),
            ('h=!0,c.abort(),b(Error(`ChatGPT browser stage timed out: ${t}`))',
             'h=!0,codexWebJournalTrace(e,"stage_timeout",{stage:t,budgetMs:r,elapsedMs:Math.round(performance.now()-a),suspendedMs:x}),c.abort(),b(Error(`ChatGPT browser stage timed out: ${t}`))'),
            ('return console.info(`[chatgpt-web] browser turn ${e} stage=${t} completed',
             'return codexWebJournalTrace(e,"stage_completed",{stage:t}),console.info(`[chatgpt-web] browser turn ${e} stage=${t} completed'),
            ('catch(m){let C=m;if(h&&i&&p)',
             'catch(m){codexWebJournalTrace(e,"stage_failed",{stage:t,kind:codexWebDiagnosticKind(m)});let C=m;if(h&&i&&p)'),
            ('Mo=(e)=>{if(ko)return;ko=e,St()}',
             'Mo=(e)=>{codexWebJournalAll("helper_transport_failed");if(ko)return;ko=e,St()}'),
            ('let n=await Te(U(e.evaluate(', 'let n=await codexWebObserveSubmission(e,()=>Te(U(e.evaluate('),
            ('),r)),o=n.snapshot??t?.snapshot', '),r))),o=n.snapshot??t?.snapshot'),
            ('let a=n?.snapshot();if(a&&n&&i?.needs', 'let a=n?.snapshot();codexWebSendProgress(e,a);if(a&&n&&i?.needs'),
            ('let c=await this.currentSubmissionAnswerText(e,t,r);',
             'let c=await codexWebSendStep(e,"tool_answer_observation",()=>this.currentSubmissionAnswerText(e,t,r));'),
            ('await n.acknowledgeToolBatch(a.lastToolBatchRevision)',
             'await codexWebSendStep(e,"tool_batch_ack",()=>n.acknowledgeToolBatch(a.lastToolBatchRevision))'),
            ('await Ae(e),await ge(e);',
             'await codexWebSendStep(e,"session_check",()=>Ae(e)),await codexWebSendStep(e,"rate_limit_check",()=>ge(e));'),
            ('let h=await U(Promise.race([',
             'let h=await codexWebSendStep(e,"submission_race",()=>U(Promise.race(['),
            (']),r);if(h.kind', ']),r));if(h.kind'),
            ('if(a&&a.lastToolBatchRevision>o)return"mcp_tool_call";',
             'if(a&&a.lastToolBatchRevision>o)return codexWebSendRecord(e,"tool_evidence"),"mcp_tool_call";'),
            ('if(s)return s;await this.waitForTurnDomOrExternalProgress',
             'if(s)return codexWebSendRecord(e,"dom_evidence",{kind:s}),s;await this.waitForTurnDomOrExternalProgress'),
            ('await this.waitForTurnDomOrExternalProgress(e,a?.revision??0,n,r)',
             'await codexWebSendStep(e,"external_wait",()=>this.waitForTurnDomOrExternalProgress(e,a?.revision??0,n,r))'),
            ('if(l+=1,l>dt)throw Error(`ChatGPT submission DOM remained unresponsive after ${dt} same-page rebinds`,{cause:h});let p=await a(l,h,c,r);s=p.page,c=p.baseline',
             'if(l+=1,codexWebSendRecord(s,"dom_rebind_attempt",{count:l}),l>dt)throw Error(`ChatGPT submission DOM remained unresponsive after ${dt} same-page rebinds`,{cause:h});let p=await a(l,h,c,r);codexWebSendMove(s,p.page);s=p.page,c=p.baseline'),
            ('await r?.("send-ready");let p=o?.snapshot().lastToolBatchRevision??0;await i?.onSendActivated?.(),await l.press("Enter",{noWaitAfter:!0,signal:n,timeout:0});let m=await this.waitForSubmissionAcceptedWithRecovery(e,t,n,o,p,a,s);return await i?.onSubmitted?.(),m',
             'await codexWebSendStep(e,"ready_capture",()=>r?.("send-ready"));codexWebSendRecord(e,"baseline",{userTurns:t.domCache?.snapshot?.userTurnCount??null,assistantTurns:t.domCache?.snapshot?.assistantTurnCount??null,composerChars:t.domCache?.snapshot?.composerChars??null});let p=o?.snapshot().lastToolBatchRevision??0;codexWebSendRecord(e,"activation_started");try{await i?.onSendActivated?.()}catch(error){codexWebSendRecord(e,"activation_failed",{kind:error?.name==="AbortError"?"aborted":"other"});throw error}codexWebSendRecord(e,"activation_completed");codexWebSendRecord(e,"press_started");try{await l.press("Enter",{noWaitAfter:!0,signal:n,timeout:0})}catch(error){codexWebSendRecord(e,"press_failed",{kind:error?.name==="AbortError"?"aborted":"other"});throw error}codexWebSendRecord(e,"press_completed");let m;try{m=await this.waitForSubmissionAcceptedWithRecovery(e,t,n,o,p,a,s)}catch(error){codexWebSendRecord(e,"submission_failed",{kind:error?.name==="AbortError"?"aborted":error?.name==="ChatGptBrowserObservationTimeoutError"?"dom_timeout":"other"});throw error}codexWebSendRecord(e,"submission_confirmed",{kind:m});return await i?.onSubmitted?.(),m'),
            ('snapshot:{userTurnCount:y.length,assistantTurnCount:b.length,visibleStopButtonCount:',
             'snapshot:{composerChars:(()=>{let q=document.querySelector(i.composerSelector);return(q instanceof HTMLTextAreaElement||q instanceof HTMLInputElement?q.value:q?.textContent??"").length})(),userTurnCount:y.length,assistantTurnCount:b.length,visibleStopButtonCount:'),
            ('attributeFilter:[...Dr]}),r))', 'attributeFilter:[...Dr],composerSelector:Ve}),r))'),
            ('return o}async currentSubmissionEvidence(',
             'codexWebSendRecord(e,"dom_state",{userTurns:o.userTurnCount,assistantTurns:o.assistantTurnCount,composerChars:o.composerChars,visibleStopButtons:o.visibleStopButtonCount});return o}async currentSubmissionEvidence('),
            (CAPTURE_ANCHOR + '...r?.diagnostic?.detail||r?.diagnostic?.detailCaptureFailed?{markdownConflict:r.diagnostic}:{},',
             CAPTURE_ANCHOR + '...r?.diagnostic?.detail||r?.diagnostic?.detailCaptureFailed?{markdownConflict:r.diagnostic}:{},...codexWebSendCapture(e)&&["send-accepted","turn-failed","turn-completed"].includes(t)?{sendDiagnostic:codexWebSendCapture(e)}:{},...codexWebCompletionCapture(e)&&["response-stalled-60s","turn-failed","turn-completed"].includes(t)?{completionDiagnostic:codexWebCompletionCapture(e)}:{},'),
            ('d.observer=new MutationObserver(()=>{d.revision+=1})',
             'd.observer=new MutationObserver(()=>{d.revision+=1,d.lastMutationAt=Date.now()})'),
            ('let r=await t.count()?await t.evaluate((o)=>{',
             'let r=await t.count()?await t.evaluate((o,selectors)=>{'),
            (STALL_CONTROLS_OLD, STALL_CONTROLS_NEW),
            ('return{textChars:(i.innerText??i.textContent??"").trim().length,htmlChars:i.innerHTML.length,descriptors:a}}):{text:"",descriptors:[]}',
             'return{textChars:(i.innerText??i.textContent??"").trim().length,htmlChars:i.innerHTML.length,descriptors:a,targetCandidateCounts:{total:aNodes.length,retained:a.length},rawAnswer:(i.innerText??i.textContent??"").trim(),lastMutationAt:globalThis.__CODEX_WEB_GPT_RESPONSE_OBSERVERS__?.states?.get(i)?.lastMutationAt??null,matchedActionCount:i.querySelectorAll(selectors.completion).length,targetTurnOrdinal:[...document.querySelectorAll(selectors.assistant)].indexOf(i),targetIsLastAssistant:[...document.querySelectorAll(selectors.assistant)].at(-1)===i}},{completion:Sr,assistant:ct}):{text:"",descriptors:[]}'),
            ('return ht(JSON.stringify({response:r,overlays:n}))}async runExclusive(',
             'let v=await e.locator(Sr).evaluateAll((controls)=>({total:controls.length,visible:controls.filter((item)=>{let style=getComputedStyle(item);return style.display!=="none"&&style.visibility!=="hidden"}).length})).catch(()=>null);if(r.rawAnswer!==void 0){r.answerFingerprint=Xe.createHmac("sha256",Xe.randomBytes(32)).update(r.rawAnswer).digest("hex");delete r.rawAnswer}return ht(JSON.stringify({response:r,overlays:n,globalActions:v}))}async runExclusive('),
            ('d=!0,await l.capture(w,"response-stalled-60s");let re=await this.stalledTurnDiagnostic(w,me.locator).catch((j)=>JSON.stringify({diagnosticError:j instanceof Error?j.message:String(j)}));console.warn(',
             'd=!0;let re=await this.stalledTurnDiagnostic(w,me.locator).catch((j)=>JSON.stringify({diagnosticError:j instanceof Error?j.message:String(j)}));codexWebStoreCompletion(w,re);await l.capture(w,"response-stalled-60s");console.warn('),
            ('return{location:{origin:be.origin',
             'return{__completionShape:' + COMPLETION_SHAPE + ',location:{origin:be.origin'),
            ('completionActionSelector:x,appName:G})=>{',
             'completionActionSelector:x,appName:G,checkpointName:diagnosticCheckpoint})=>{'),
            ('completionActionSelector:Sr,appName:this.appName}))]),c=new Date().toISOString();',
             'completionActionSelector:Sr,appName:this.appName,checkpointName:t}))]),c=new Date().toISOString();if(s.status==="fulfilled"&&s.value?.__completionShape){codexWebStoreCompletion(e,JSON.stringify(s.value.__completionShape));delete s.value.__completionShape}else if(["response-stalled-60s","turn-failed","turn-completed"].includes(t))codexWebStoreCompletion(e,JSON.stringify({diagnosticError:s.status==="rejected"&&s.reason?.name==="TimeoutError"?"timed out":"shape unavailable"}));'),
        ])
    if not legacy:
        edits.append(('...r?.diagnostic?.detail||r?.diagnostic?.detailCaptureFailed?', '...r?.diagnostic?.detail||r?.diagnostic?.reconciliation||r?.diagnostic?.detailCaptureFailed?'))
    return edits


def replacements_613() -> list[tuple[str, str]]:
    """Adapt only the verified 6.1.3 bundle anchors; retain 6.1.2 behavior."""
    edits = replacements()
    edits[5] = (
        'throw new S(g.message,{status:502,errorType:"server_error",code:"browser_stream_inconsistent",retryable:!1})',
        '{const diagnosticError=new S(g.message,{status:502,errorType:"server_error",code:"browser_stream_inconsistent",retryable:!1});diagnosticError.diagnostic=g.diagnostic;throw diagnosticError}',
    )
    edits[7] = tuple(value.replace('ee.send', 'te.send').replace('await we()', 'await be()') for value in edits[7])
    edits[8] = tuple(value.replace('Ae(e)', 'Se(e)').replace('ge(e)', 'we(e)') for value in edits[8])
    edits[10] = ('L=new Po,H=new ur,C=', 'L=new Po,H=codexWebBindReconciliation(new ur,w),C=')
    edits[14] = ('h,p,m,T=[],x=new xo;try{',
                 'h,p,m,T=[],x=new xo;codexWebJournalOpen(l,e.abortSignal);try{')
    edits[17] = ('finally{if(x.dispose(),', 'finally{codexWebJournalClose(l);if(x.dispose(),')
    edits[21] = ('catch(m){let T=m;if(h&&i&&p)',
                 'catch(m){codexWebJournalTrace(e,"stage_failed",{stage:t,kind:codexWebDiagnosticKind(m)});let T=m;if(h&&i&&p)')
    edits[23] = tuple(value.replace('Te(U(e.evaluate(', 'xe(U(e.evaluate(') for value in edits[23])
    edits[28] = tuple(value.replace('Ae(e)', 'Se(e)').replace('ge(e)', 'we(e)') for value in edits[28])
    edits[36] = tuple(value.replace('userTurnCount:y.length', 'userTurnCount:x.length') for value in edits[36])
    edits[45] = (
        'd=!0,await l.capture(w,"response-stalled-60s");let oe=await this.stalledTurnDiagnostic(w,fe.locator).catch((K)=>JSON.stringify({diagnosticError:K instanceof Error?K.message:String(K)}));console.warn(',
        'd=!0;let oe=await this.stalledTurnDiagnostic(w,fe.locator).catch((K)=>JSON.stringify({diagnosticError:K instanceof Error?K.message:String(K)}));codexWebStoreCompletion(w,oe);await l.capture(w,"response-stalled-60s");console.warn(',
    )
    shape = (COMPLETION_SHAPE.replace('node.matches(x)', 'node.matches(v)')
             .replace('node.closest(y)', 'node.closest(x)')
             .replace('querySelectorAll(x)', 'querySelectorAll(v)')
             .replace('all.filter(_)', 'all.filter(E)')
             .replace(".filter(_).slice(-20)", ".filter(E).slice(-20)"))
    edits[46] = ('return{location:{origin:Ce.origin',
                 'return{__completionShape:' + shape + ',location:{origin:Ce.origin')
    edits[47] = ('completionActionSelector:v,appName:R})=>{',
                 'completionActionSelector:v,appName:R,checkpointName:diagnosticCheckpoint})=>{')
    return edits


def transform(data: bytes, *, reverse: bool = False, legacy: bool = False,
              version: str = "6.1.2") -> bytes:
    text = data.decode("utf-8")
    edits = replacements_613() if version == "6.1.3" else replacements(legacy=legacy)
    for old, new in reversed(edits) if reverse else edits:
        before, after = (new, old) if reverse else (old, new)
        if text.count(before) != 1:
            raise ValueError("补丁定位不唯一或文件不兼容；未写入。")
        text = text.replace(before, after, 1)
    return text.encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect(data: bytes, original_hint: bytes | None = None,
            version: str = "6.1.2") -> tuple[str, bytes]:
    original_hash = ORIGINAL_613_SHA256 if version == "6.1.3" else ORIGINAL_SHA256
    if digest(data) == original_hash:
        return "original", data
    if digest(data) in (ORIGINAL_SHA256, ORIGINAL_613_SHA256):
        raise ValueError("目标软件版本与程序文件不匹配。")
    if version == "6.1.2" and digest(data) in (PREVIOUS_PATCH_SHA256, SECOND_PATCH_SHA256,
            THIRD_PATCH_SHA256, FOURTH_PATCH_SHA256, FIFTH_PATCH_SHA256):
        if original_hint is not None and digest(original_hint) == original_hash:
            return "previous_patch", original_hint
        raise ValueError("上一版诊断补丁需要对应的官方原件备份；拒绝覆盖。")
    candidates = ((False, "patched"),) if version == "6.1.3" else ((False, "patched"), (True, "legacy_patch"))
    for legacy, label in candidates:
        try:
            original = transform(data, reverse=True, legacy=legacy, version=version)
            if digest(original) == original_hash:
                return label, original
        except (ValueError, UnicodeError):
            pass
    raise ValueError(f"文件指纹不匹配：仅支持未经修改的 {version} Windows x64 文件及本补丁。")


def replace_file(target: Path, expected: bytes, content: bytes) -> None:
    # Keep the original on any write failure; stage on the same filesystem.
    descriptor, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    staging = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staging, stat.S_IMODE(target.stat().st_mode))
        if target.is_symlink() or target.read_bytes() != expected:
            raise ValueError("目标在操作期间变化；拒绝覆盖。")
        os.replace(staging, target)
    finally:
        staging.unlink(missing_ok=True)


def operate(action: str, target: Path, backup: Path) -> str:
    if target.is_symlink() or backup.is_symlink():
        raise ValueError("目标和备份不能是符号链接。")
    target, backup = target.resolve(), backup.resolve()
    if target.name != "browser-helper.cjs":
        raise ValueError("目标必须是 browser-helper.cjs。")
    package = json.loads(target.with_name("package.json").read_text(encoding="utf-8"))
    version = package.get("version")
    if package.get("name") != "codex-chatgpt-web" or version not in ("6.1.2", "6.1.3"):
        raise ValueError("目标软件名称或版本不匹配。")
    if backup.is_relative_to(target.parent.parent):
        raise ValueError("备份必须放在版本目录之外，避免被启动器恢复程序时移除。")
    current = target.read_bytes()
    state, original = inspect(current, backup.read_bytes() if backup.is_file() else None, version)
    if backup.exists() and backup.read_bytes() != original:
        raise ValueError("已有备份不匹配；拒绝覆盖备份和目标。")
    if action == "check":
        return state
    if action == "apply":
        patched = transform(original, version=version)
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb") as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
        if state == "patched":
            return "already_patched"
        replace_file(target, current, patched)
        return "applied"
    if action == "restore":
        if state == "original":
            return "already_original"
        if not backup.is_file():
            raise ValueError("原始备份不存在；拒绝撤回。")
        replace_file(target, current, backup.read_bytes())
        return "restored"
    raise ValueError("未知操作。")


def patched_manifest(original: bytes, patched_helper: bytes) -> bytes:
    manifest = json.loads(original)
    files = manifest["files"]
    entry = next(file for file in files if file["path"] == "app/browser-helper.cjs")
    entry["size"] = len(patched_helper)
    entry["sha256"] = digest(patched_helper)
    bundle = hashlib.sha256()
    for file in files:
        for field in (file["path"], "\0", str(file["size"]), "\0", file["sha256"], "\0"):
            bundle.update(field.encode())
    manifest["bundleId"] = bundle.hexdigest()
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()


def operate_package(action: str, target: Path, backup: Path, manifest_path: Path, manifest_backup: Path) -> str:
    if any(path.is_symlink() for path in (target, backup, manifest_path, manifest_backup)):
        raise ValueError("目标和备份不能是符号链接。")
    target, backup, manifest_path, manifest_backup = map(Path.resolve, (target, backup, manifest_path, manifest_backup))
    runtime_root = target.parent.parent
    if manifest_path != runtime_root / "manifest.json":
        raise ValueError("清单必须属于目标所在的运行包。")
    if backup.is_relative_to(runtime_root) or manifest_backup.is_relative_to(runtime_root):
        raise ValueError("备份必须放在运行包之外。")
    if target.name != "browser-helper.cjs":
        raise ValueError("目标必须是 browser-helper.cjs。")
    package = json.loads(target.with_name("package.json").read_text(encoding="utf-8"))
    version = package.get("version")
    if package.get("name") != "codex-chatgpt-web" or version not in ("6.1.2", "6.1.3"):
        raise ValueError("目标软件名称或版本不匹配。")
    current_helper, current_manifest = target.read_bytes(), manifest_path.read_bytes()
    helper_state, original_helper = inspect(current_helper, backup.read_bytes() if backup.is_file() else None, version)
    original_manifest_hash = ORIGINAL_613_MANIFEST_SHA256 if version == "6.1.3" else ORIGINAL_MANIFEST_SHA256
    if digest(current_manifest) == original_manifest_hash:
        manifest_state, original_manifest = "original", current_manifest
    elif manifest_backup.is_file() and digest(manifest_backup.read_bytes()) == original_manifest_hash:
        original_manifest = manifest_backup.read_bytes()
        manifest_state = "patched" if current_manifest == patched_manifest(original_manifest, current_helper) else "unknown"
    else:
        raise ValueError("清单不是官方原件或本补丁生成的清单；拒绝覆盖。")
    if manifest_state == "unknown" or (helper_state == "original") != (manifest_state == "original"):
        raise ValueError("程序文件与清单状态不一致；拒绝覆盖。")
    if backup.exists() and backup.read_bytes() != original_helper:
        raise ValueError("程序文件备份不匹配。")
    if manifest_backup.exists() and manifest_backup.read_bytes() != original_manifest:
        raise ValueError("清单备份不匹配。")
    if action == "check":
        return helper_state
    if action == "apply" and helper_state == "patched":
        return "already_patched"
    if action == "restore" and helper_state == "original":
        return "already_original"
    for path, data in ((backup, original_helper), (manifest_backup, original_manifest)):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
    next_helper = transform(original_helper, version=version) if action == "apply" else original_helper
    next_manifest = patched_manifest(original_manifest, next_helper) if action == "apply" else original_manifest
    replace_file(target, current_helper, next_helper)
    try:
        replace_file(manifest_path, current_manifest, next_manifest)
    except Exception:
        replace_file(target, next_helper, current_helper)
        raise
    return "applied" if action == "apply" else "restored"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "apply", "restore"))
    parser.add_argument("--target", required=True, type=Path, help="明确指定 browser-helper.cjs")
    parser.add_argument("--backup", required=True, type=Path, help="版本目录之外的原始备份位置")
    parser.add_argument("--manifest", type=Path, help="安装目录中的运行包清单")
    parser.add_argument("--manifest-backup", type=Path, help="运行包之外的原始清单备份")
    arguments = parser.parse_args()
    try:
        if bool(arguments.manifest) != bool(arguments.manifest_backup):
            raise ValueError("清单路径与清单备份必须同时提供。")
        result = (operate_package(arguments.action, arguments.target, arguments.backup,
                                  arguments.manifest, arguments.manifest_backup)
                  if arguments.manifest else operate(arguments.action, arguments.target, arguments.backup))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps({"status": result, "target": str(arguments.target.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
