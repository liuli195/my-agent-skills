/*
MIT License

Copyright (c) 2026 codex-chatgpt-web contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
// Frozen reconciliation excerpt from miuuyy/codex-chatgpt-web v6.1.2.
// Source: src/adapters/chatgpt-web/markdown.ts; upstream MIT license.
// HTML conversion is supplied by the test; reconciliation below is unmodified.
class je extends Error{diagnostic;constructor(e,t){super(e);this.diagnostic=t;this.name="ChatGptMarkdownConsistencyError"}}class ur{transform;stabilityMs;candidates=new Map;committed=[];latest=[];markdown="";lastGroup;consistencyError;constructor(e=(r)=>r,t=750){this.transform=e;this.stabilityMs=t;if(!Number.isFinite(t)||t<0)throw Error("ChatGPT Markdown stability window must be a non-negative finite number")}observe(e,t=Date.now()){let r=this.reconcile(e);if(r instanceof je)return this.consistencyError=r,"";this.consistencyError=void 0,this.latest=r.map((a)=>({...a}));let n=new Set;for(let a of r){let s=this.candidateId(a);n.add(s);let c=this.candidates.get(s),l=c&&c.key===a.key&&c.tag===a.tag&&c.html===a.html&&c.text===a.text&&c.group===a.group&&c.sourceStart===a.sourceStart&&c.sourceEnd===a.sourceEnd;this.candidates.set(s,{...a,changedAt:l?c.changedAt:t,...a.streamable?{streamableAt:l&&c.streamableAt!==void 0?c.streamableAt:t}:{}})}for(let a of this.candidates.keys())if(!n.has(a))this.candidates.delete(a);let o="",i=0;while(i<r.length){let a=r[i],s=this.candidateId(a),c=this.candidates.get(s);if(!c?.streamable||c.streamableAt===void 0)break;if(t-Math.max(c.changedAt,c.streamableAt)<this.stabilityMs)break;o+=this.commit(c),this.committed.push(this.committedSegment(c)),this.candidates.delete(s),i+=1}return this.latest=this.latest.slice(i),o}finish(){if(this.consistencyError)throw this.consistencyError;let e="";for(let t of this.latest)e+=this.commit(t),this.committed.push(this.committedSegment(t));return this.candidates.clear(),this.latest=[],{markdown:this.markdown,delta:e}}currentSnapshotIsConsistent(){return this.consistencyError===void 0}reconcile(e){if(this.committed.length===0||e.length===0)return e;let t=[],r=this.committed.filter((s)=>s.sourceEnd!==void 0).at(-1),n=r?.sourceEnd,o=-1,i=!1,a;for(let s of e){if(s.sourceStart!==void 0){if(a!==void 0&&s.sourceStart<=a)return new je("ChatGPT final DOM exposed non-monotonic source ranges");a=s.sourceStart}let c=this.committedIndex(s);if(c!==void 0){let h=this.committed[c];if(i||c<o||h.text!==s.text)return this.changedCommittedBlockError(i||c<o?"block_order_changed":"text_changed",s,h);if(o=c,JSON.stringify(h.linkTargets??[])!==JSON.stringify(s.linkTargets??[]))return this.changedCommittedBlockError("link_target_changed",s,h);continue}if(s.sourceStart!==void 0&&n!==void 0){if(s.sourceStart<=n)return this.changedCommittedBlockError("source_range_overlap",s,r);i=!0,t.push(s);continue}if(o!==this.committed.length-1&&!this.matchesLatestPending(s))return new je("ChatGPT final DOM could not be aligned with text already streamed to Codex");i=!0,t.push(s)}return t}committedIndex(e){let t=this.committed.findIndex((n)=>e.sourceStart!==void 0&&n.sourceStart!==void 0?e.sourceStart===n.sourceStart&&e.tag===n.tag:e.key===n.key);if(t>=0)return t;if(e.sourceStart!==void 0)return;if(!e.tag)return;if(!e.text.trim())return;let r=this.committed.map((n,o)=>({committed:n,index:o})).filter(({committed:n})=>n.tag===e.tag&&n.text===e.text);return r.length===1?r[0].index:void 0}matchesLatestPending(e){if(this.latest.filter((r)=>e.sourceStart!==void 0&&r.sourceStart!==void 0?e.sourceStart===r.sourceStart&&e.tag===r.tag:e.key===r.key).length===1)return!0;if(e.sourceStart!==void 0)return!1;if(!e.tag)return!1;if(!e.text.trim())return!1;return this.latest.filter((r)=>r.tag===e.tag&&r.text===e.text).length===1}candidateId(e){return e.sourceStart!==void 0?`source:${e.sourceStart}:${e.tag??""}`:`key:${e.key}`}committedSegment(e){return{key:e.key,...e.tag?{tag:e.tag}:{},text:e.text,...e.linkTargets?{linkTargets:[...e.linkTargets]}:{},...e.sourceStart!==void 0?{sourceStart:e.sourceStart}:{},...e.sourceEnd!==void 0?{sourceEnd:e.sourceEnd}:{}}}changedCommittedBlockError(e,t,r){return new je("ChatGPT changed a completed text block that was already streamed to Codex",{reason:e,observedStart:t.sourceStart,observedEnd:t.sourceEnd,committedStart:r.sourceStart,committedEnd:r.sourceEnd,observedTextChars:t.text.length,committedTextChars:r.text.length})}commit(e){let t=this.transform(hi(e.html));if(!t)return"";let n=`${this.markdown?e.group!==void 0&&e.group===this.lastGroup?`
`:`

`:""}${t}`;return this.markdown+=n,this.lastGroup=e.group,n}}