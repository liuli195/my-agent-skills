"""Exercise the patch's public entry and the unchanged upstream consistency guard."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/codex-web-diagnostics/patch.py"
FIXTURE = ROOT / "tests/fixtures/codex_web_markdown_6_1_2.cjs"
spec = importlib.util.spec_from_file_location("diagnostic_patch", SCRIPT)
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


@pytest.fixture
def sample(tmp_path, monkeypatch):
    target = tmp_path / "version/app/browser-helper.cjs"
    target.parent.mkdir(parents=True)
    target.with_name("package.json").write_text(json.dumps({"name": "codex-chatgpt-web", "version": "6.1.2"}))
    original = (FIXTURE.read_text(encoding="utf-8") + "\n"
                + 'class k extends Error {constructor(message, options){super(message);Object.assign(this,options)}}\n'
                + 'function convert(f){' + patch.OLD_THROW + '}\n'
                + 'function capture(r){let t="turn-failed";return {' + patch.CAPTURE_ANCHOR + '}}\n').encode()
    target.write_bytes(original)
    monkeypatch.setattr(patch, "ORIGINAL_SHA256", patch.digest(original))
    original_replacements = patch.replacements
    monkeypatch.setattr(patch, "replacements", lambda *, legacy=False: original_replacements(legacy=True))
    return target, tmp_path / "backup/helper.original", original


def test_apply_repeat_restore_and_changed_target_refusal(sample):
    target, backup, original = sample
    assert patch.operate("check", target, backup) == "original"
    assert not backup.exists()
    assert patch.operate("apply", target, backup) == "applied"
    patched = target.read_bytes()
    assert patch.operate("apply", target, backup) == "already_patched"
    assert target.read_bytes() == patched
    assert backup.read_bytes() == original
    target.write_bytes(patched + b"// other modification")
    with pytest.raises(ValueError):
        patch.operate("restore", target, backup)
    assert target.read_bytes() == patched + b"// other modification"
    target.write_bytes(patched)
    assert patch.operate("restore", target, backup) == "restored"
    assert target.read_bytes() == original
    assert patch.operate("restore", target, backup) == "already_original"


def test_backup_version_and_atomic_failure_guards(sample, monkeypatch):
    target, backup, original = sample
    backup.parent.mkdir()
    backup.write_bytes(b"wrong backup")
    with pytest.raises(ValueError):
        patch.operate("apply", target, backup)
    assert target.read_bytes() == original
    backup.write_bytes(original)
    with pytest.raises(ValueError):
        patch.operate("apply", target, target.with_suffix(".backup"))
    target.with_name("package.json").write_text('{"name":"codex-chatgpt-web","version":"6.1.3"}')
    with pytest.raises(ValueError):
        patch.operate("apply", target, backup)
    target.with_name("package.json").write_text('{"name":"codex-chatgpt-web","version":"6.1.2"}')
    def fail_replace(*_):
        raise OSError("simulated disk failure")
    monkeypatch.setattr(patch.os, "replace", fail_replace)
    with pytest.raises(OSError):
        patch.operate("apply", target, backup)
    assert target.read_bytes() == original
    assert backup.read_bytes() == original
    assert not list(target.parent.glob("*.tmp"))


def test_previous_patch_requires_matching_official_backup(sample, monkeypatch):
    target, backup, original = sample
    previous = b"exact prior diagnostic patch"
    monkeypatch.setattr(patch, "PREVIOUS_PATCH_SHA256", patch.digest(previous))
    target.write_bytes(previous)
    with pytest.raises(ValueError, match="官方原件备份"):
        patch.operate("check", target, backup)
    backup.parent.mkdir()
    backup.write_bytes(original)
    assert patch.operate("check", target, backup) == "previous_patch"
    assert patch.operate("apply", target, backup) == "applied"
    assert patch.operate("check", target, backup) == "patched"
    assert patch.operate("restore", target, backup) == "restored"
    assert target.read_bytes() == original


def test_real_guard_differential_and_private_local_capture(sample):
    target, backup, original = sample
    patch.operate("apply", target, backup)
    runner = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [originalPath,patchedPath]=process.argv.slice(1);
const load=(path,failHash=false)=>vm.runInNewContext(fs.readFileSync(path,'utf8')+
  ';({Stream:ur,convert,capture})',{
  hi:html=>html, ht:message=>message,
  require:name=>{if(failHash)throw Error('hashing unavailable');return require(name)}
});
const old=load(originalPath),patched=load(patchedPath),broken=load(patchedPath,true);
const a={key:'private-key-a',tag:'p',text:'例子：',html:'例子：',streamable:true};
const b={key:'private-key-b',tag:'p',text:'private body',html:'private body',streamable:true};
const cases=[
 ['same',[a,b],[a,b],null],
 ['new',[a,b],[a,b,{...b,key:'new',text:'new body',html:'new body'}],null],
 ['repeat',[a,b],[a,b,{...a,key:'different-key'}],'block_order_changed'],
 ['reorder',[a,b],[b,a],'block_order_changed'],
 ['rewrite',[a,b],[{...a,text:'rewritten private body'},b],'text_changed'],
 ['link',[a,b],[{...a,linkTargets:['https://private.example/secret']},b],'link_target_changed'],
 ['overlap',[{...a,sourceStart:0,sourceEnd:10}],
   [{...b,sourceStart:5,sourceEnd:20}],'source_range_overlap'],
];
for(const [name,committed,observed,reason] of cases){
 const results=[old,patched,broken].map(api=>{
  const stream=new api.Stream();stream.committed=committed.map(x=>({...x}));
  const delta=stream.observe(observed,1000);
  const error=stream.consistencyError;
  assert.equal(error?.diagnostic.reason??null,reason,name);
  if(error){
   assert.throws(()=>stream.finish(),e=>e===error);
   return {delta,message:error.message,base:Object.fromEntries(Object.entries(error.diagnostic)
     .filter(([k])=>!['detail','detailCaptureFailed'].includes(k))),error};
  }
  return {delta,finished:stream.finish()};
 });
 assert.deepEqual(JSON.parse(JSON.stringify({...results[1],error:undefined})),
   JSON.parse(JSON.stringify({...results[0],error:undefined})),name);
 assert.deepEqual(JSON.parse(JSON.stringify({...results[2],error:undefined})),
   JSON.parse(JSON.stringify({...results[0],error:undefined})),name);
 if(reason){
  const error=results[1].error, detail=error.diagnostic.detail;
  assert.equal(detail.schemaVersion,1);
  assert.equal(results[2].error.diagnostic.detailCaptureFailed,true);
  if(name==='repeat'){
   assert.equal(detail.matchedBy,'unique_tag_and_text');
   assert.equal(detail.observedIndex,2);assert.equal(detail.committedIndex,0);
   assert.equal(detail.sameText,true);assert.equal(detail.sameKey,false);
   assert.equal(detail.observed[2].textFingerprint,detail.committed[0].textFingerprint);
  }
  if(name==='reorder')assert.equal(detail.matchedBy,'key');
  let converted;try{patched.convert(error)}catch(e){converted=e}
  assert.equal(converted.code,'browser_stream_inconsistent');
  assert.equal(converted.retryable,false);assert.equal(converted.status,502);
  const record=patched.capture(converted);
  assert.equal(record.markdownConflict.detail.schemaVersion,1);
  const serialized=JSON.stringify(record);
  for(const secret of ['private-key','private body','例子：','private.example','different-key'])
   assert(!serialized.includes(secret),secret);
  const again=new patched.Stream();again.committed=committed;again.observe(observed,1000);
  assert.notEqual(again.consistencyError.diagnostic.detail.observed[0].textFingerprint,
    detail.observed[0].textFingerprint);
 }
}
// A temporary conflict can recover exactly as before; recording doesn't pin it.
for(const api of [old,patched]){
 const stream=new api.Stream();stream.committed=[a,b];
 stream.observe([b,a],1000);assert(stream.consistencyError);
 stream.observe([a,b],2000);assert.equal(stream.consistencyError,undefined);
 assert.equal(stream.finish().delta,'');
}
console.log('7 behavior cases, diagnostic failure, privacy, conversion and local capture passed');
'''
    result = subprocess.run(["node", "-e", runner, str(backup), str(target)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr


def test_public_cli_on_explicit_official_reference(tmp_path):
    reference = os.environ.get("CODEX_WEB_DIAGNOSTICS_REFERENCE")
    if not reference:
        pytest.skip("Set CODEX_WEB_DIAGNOSTICS_REFERENCE for a full official-bundle smoke test")
    source = Path(reference)
    target = tmp_path / "version/app/browser-helper.cjs"
    target.parent.mkdir(parents=True)
    original = source.read_bytes()
    assert patch.digest(original) == patch.ORIGINAL_SHA256
    target.write_bytes(original)
    target.with_name("package.json").write_bytes(source.with_name("package.json").read_bytes())
    backup = tmp_path / "backup/helper.original"
    for action, expected in [("check", "original"), ("apply", "applied"), ("apply", "already_patched"),
                             ("check", "patched"), ("restore", "restored"), ("check", "original")]:
        result = subprocess.run([sys.executable, str(SCRIPT), action, "--target", str(target),
                                 "--backup", str(backup)], capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["status"] == expected
        if action == "apply":
            syntax = subprocess.run(["node", "--check", str(target)], capture_output=True, text=True)
            assert syntax.returncode == 0, syntax.stderr
    assert target.read_bytes() == original
    assert source.read_bytes() == original
    # A running installation can contain the earlier conflict-only patch.
    target.write_bytes(patch.transform(original, legacy=True))
    for action, expected in [("check", "legacy_patch"), ("apply", "applied"),
                             ("check", "patched"), ("restore", "restored")]:
        result = subprocess.run([sys.executable, str(SCRIPT), action, "--target", str(target),
                                 "--backup", str(backup)], capture_output=True, text=True, encoding="utf-8")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["status"] == expected
    assert target.read_bytes() == original
    # Upgrade the installed package's earlier patch and its checksum manifest together.
    previous_reference = os.environ.get("CODEX_WEB_DIAGNOSTICS_PREVIOUS")
    if previous_reference:
        previous = Path(previous_reference).read_bytes()
        assert patch.digest(previous) in (patch.PREVIOUS_PATCH_SHA256, patch.SECOND_PATCH_SHA256, patch.THIRD_PATCH_SHA256, patch.FOURTH_PATCH_SHA256, patch.FIFTH_PATCH_SHA256)
        target.write_bytes(previous)
        for action, expected in [("check", "previous_patch"), ("apply", "applied"),
                                 ("check", "patched"), ("restore", "restored")]:
            result = subprocess.run([sys.executable, str(SCRIPT), action, "--target", str(target),
                                     "--backup", str(backup)], capture_output=True, text=True, encoding="utf-8")
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout)["status"] == expected
        assert target.read_bytes() == original
    official_manifest = source.parent.parent / "manifest.json"
    if official_manifest.is_file():
        manifest_path = target.parent.parent / "manifest.json"
        manifest_backup = tmp_path / "backup/manifest.original"
        original_manifest = official_manifest.read_bytes()
        assert patch.digest(original_manifest) == patch.ORIGINAL_MANIFEST_SHA256
        manifest_backup.write_bytes(original_manifest)
        arguments = ["--target", str(target), "--backup", str(backup),
                     "--manifest", str(manifest_path), "--manifest-backup", str(manifest_backup)]
        prior_versions = [(patch.transform(original, legacy=True), "legacy_patch")]
        if previous_reference:
            prior_versions.append((previous, "previous_patch"))
        for old_helper, old_status in prior_versions:
            target.write_bytes(old_helper)
            manifest_path.write_bytes(patch.patched_manifest(original_manifest, old_helper))
            for action, expected in [("check", old_status), ("apply", "applied"),
                                     ("check", "patched"), ("restore", "restored")]:
                result = subprocess.run([sys.executable, str(SCRIPT), action, *arguments],
                                        capture_output=True, text=True, encoding="utf-8")
                assert result.returncode == 0, result.stderr
                assert json.loads(result.stdout)["status"] == expected
            assert target.read_bytes() == original
            assert manifest_path.read_bytes() == original_manifest


def test_live_send_evidence_survives_killed_helper(tmp_path):
    runner = r'''
const fs=require('node:fs'),vm=require('node:vm'),EventEmitter=require('node:events');
const [source,directory]=process.argv.slice(1);
const api=vm.runInNewContext(fs.readFileSync(source,'utf8')+
 ';({open:codexWebJournalOpen,bind:codexWebJournalBind,start:codexWebSendStart,step:codexWebSendStep})',
 {require,process,console,performance});
const capture={traceId:'killed-helper',directory},page=new EventEmitter();
api.open(capture);api.bind(capture,page);api.start(page,'private prompt must not leak');
api.step(page,'press',()=>new Promise(()=>{}));
console.log('WAITING');setInterval(()=>{},1000);
'''
    child = subprocess.Popen(["node", "-e", runner, str(patch.PATCH_SOURCE), str(tmp_path)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "WAITING"
        snapshot = tmp_path / "send-1-live.json"
        before = snapshot.read_bytes()
        proof = json.loads(before)
        assert proof["schemaVersion"] == 4
        assert proof["sendDiagnostic"]["events"][-1]["phase"] == "press_started"
        assert "private prompt" not in before.decode()
        child.kill()
        child.wait(timeout=10)
        assert snapshot.read_bytes() == before
        assert not list(tmp_path.glob("*-turn-failed.json"))
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)


def test_send_button_wait_records_disabled_state_without_writing_every_poll(tmp_path):
    runner = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=require('node:path');
const [source,directory]=process.argv.slice(1);
let now=0;
const api=vm.runInNewContext(fs.readFileSync(source,'utf8')+
 ';({open:codexWebJournalOpen,bind:codexWebJournalBind,start:codexWebSendStart,'+
 'step:codexWebSendStep,button:codexWebSendButtonCheck,send:codexWebSendCapture})',
 {require,process,console,performance:{now:()=>now}});
const capture={traceId:'button-wait',directory},page={on(){},off(){},context:()=>null};
const read=()=>JSON.parse(fs.readFileSync(path.join(directory,'send-1-live.json'),'utf8'));
(async()=>{
 api.open(capture);api.bind(capture,page);api.start(page,'private prompt');
 assert.equal(await api.step(page,'active_composer',async()=>42),42);
 assert.equal(await api.step(page,'button_visible',async()=>42),42);
 for(let i=0;i<10;i++){
   now+=20;
   await api.step(page,'button_session_check',async()=>{});
   await api.step(page,'button_rate_limit_check',async()=>{});
   assert.equal(await api.button(page,async()=>false),false);
 }
 assert.equal(api.send(page).milestones.button_enabled_check_completed.count,10);
 assert.equal(api.send(page).eventCount,65);
 assert(read().sendDiagnostic.eventCount<65);
 now+=1000;
 assert.equal(await api.button(page,async()=>true),true);
 assert.equal(read().sendDiagnostic.events.at(-1).enabled,true);
 assert.equal(read().sendDiagnostic.events.at(-1).phase,'button_enabled_check_completed');
 assert(!JSON.stringify(read()).includes('private prompt'));
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", runner, str(patch.PATCH_SOURCE), str(tmp_path)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_live_send_lifecycle_and_disk_failure_preserve_original_behavior(tmp_path):
    runner = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const path=require('node:path'),EventEmitter=require('node:events');
const [source,directory]=process.argv.slice(1);
let fail=false,warnings=0;
const wrappedFs=new Proxy(fs,{get:(target,key)=>key==='renameSync'?
 (...args)=>{if(fail)throw Error('private path');return target[key](...args)}:target[key]});
const api=vm.runInNewContext(fs.readFileSync(source,'utf8')+
 ';({open:codexWebJournalOpen,bind:codexWebJournalBind,close:codexWebJournalClose,'+
 'trace:codexWebJournalTrace,start:codexWebSendStart,step:codexWebSendStep,'+
 'move:codexWebSendMove,record:codexWebSendRecord})',
 {require:name=>name==='node:fs'?wrappedFs:require(name),process,performance,
 console:{warn:()=>warnings++}});
const capture={traceId:'lifecycle',directory},page=new EventEmitter();
const browser=new EventEmitter();page.context=()=>({browser:()=>browser});
const abort=new AbortController(),exitListeners=process.listenerCount('exit');
const read=name=>JSON.parse(fs.readFileSync(path.join(directory,name),'utf8'));
(async()=>{
 api.open(capture,abort.signal);api.bind(capture,page);api.bind(capture,page);
 assert.equal(page.listenerCount('close'),1);
 api.start(page,'secret prompt');
 assert.equal(await api.step(page,'press',async()=>42),42);
 const before=fs.readFileSync(path.join(directory,'send-1-live.json'),'utf8');
 fail=true;
 const original=Error('private failure');
 await assert.rejects(api.step(page,'session_check',async()=>{throw original}),e=>e===original);
 assert.equal(fs.readFileSync(path.join(directory,'send-1-live.json'),'utf8'),before);
 assert.equal(warnings,1);assert(!fs.existsSync(path.join(directory,'send-1-live.json.tmp')));
 fail=false;
 api.record(page,'press_completed');
 assert(read('send-1-live.json').writeFailures>=2);
 abort.abort(Error('private reason'));
 assert.equal(read('turn-live.json').phase,'turn_abort');
 page.emit('close');assert.equal(read('turn-live.json').phase,'page_close');
 browser.emit('disconnected');assert.equal(read('turn-live.json').phase,'browser_disconnected');
 const next=new EventEmitter();api.move(page,next);
 api.record(next,'dom_read_started');
 assert.equal(read('send-1-live.json').sendDiagnostic.events.at(-1).phase,'dom_read_started');
 const first=fs.readFileSync(path.join(directory,'send-1-live.json'),'utf8');
 api.start(next,'second private prompt');
 assert.equal(read('send-2-live.json').sendNumber,2);
 assert.equal(fs.readFileSync(path.join(directory,'send-1-live.json'),'utf8'),first);
 for(let i=0;i<100;i++)api.record(next,'dom_read_completed',{count:i});
 assert.equal(read('send-2-live.json').sendDiagnostic.events.length,40);
 assert(read('send-2-live.json').events.length<=40);
 assert(read('send-2-live.json').events.some(event=>event.phase==='turn_abort'));
 api.close(capture);
 assert.equal(page.listenerCount('close'),0);assert.equal(next.listenerCount('close'),0);
 assert.equal(browser.listenerCount('disconnected'),0);
 assert.equal(process.listenerCount('exit'),exitListeners);
 for(const file of fs.readdirSync(directory)){
   const raw=fs.readFileSync(path.join(directory,file),'utf8');
   assert(!/private|secret prompt/.test(raw),file);
 }
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", runner, str(patch.PATCH_SOURCE), str(tmp_path)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_official_stage_timeout_records_before_pending_operation_returns(tmp_path):
    reference = os.environ.get("CODEX_WEB_DIAGNOSTICS_REFERENCE")
    if not reference:
        pytest.skip("Set CODEX_WEB_DIAGNOSTICS_REFERENCE for official stage timeout coverage")
    source = patch.transform(Path(reference).read_bytes()).decode("utf-8")
    start = source.index("async runStage(")
    method = source[start:source.index("async ensurePage(", start)]
    method_file = tmp_path / "stage.js"
    method_file.write_text(method, encoding="utf-8")
    runner = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const EventEmitter=require('node:events'),path=require('node:path');
const [source,method,directory]=process.argv.slice(1);
const api=vm.runInNewContext(fs.readFileSync(source,'utf8')+
 ';class Runner{'+fs.readFileSync(method,'utf8')+'};'+
 '({Runner,open:codexWebJournalOpen,bind:codexWebJournalBind,close:codexWebJournalClose,'+
 'start:codexWebSendStart,step:codexWebSendStep})',
 {require,process,performance,console:{info(){},error(){},warn(){}},setTimeout,clearTimeout,AbortController,
  xt:{start(){},suspendedMs:()=>0},_a:(budget,elapsed,suspended)=>budget-elapsed+suspended,
  xe:class extends Error{}});
const capture={traceId:'stage-timeout',directory},page=new EventEmitter();
(async()=>{
 api.open(capture);api.bind(capture,page);api.start(page,'private prompt');
 let aborted=false;
 await assert.rejects(new api.Runner().runStage(capture.traceId,'send',10,signal=>{
   signal.addEventListener('abort',()=>{aborted=true});
   return api.step(page,'session_check',()=>new Promise(()=>{}));
 }),/ChatGPT browser stage timed out: send/);
 assert(aborted);
 const proof=JSON.parse(fs.readFileSync(path.join(directory,'turn-live.json'),'utf8'));
 assert(proof.events.some(event=>event.phase==='stage_timeout'&&event.stage==='send'));
 assert.equal(proof.sendDiagnostic.milestones.session_check_started.count,1);
 assert.equal(proof.sendDiagnostic.milestones.session_check_completed,undefined);
 api.close(capture);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", runner, str(patch.PATCH_SOURCE), str(method_file),
                             str(tmp_path / "diagnostics")], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_reconciliation_history_and_anonymous_replay(tmp_path):
    source = FIXTURE.read_text(encoding="utf-8")
    # Exercise the frozen real matcher plus only the new diagnostic wrappers.
    source = patch.PATCH_SOURCE.read_text(encoding="utf-8") + source
    for before, after in patch.replacements():
        if before.startswith(("reconcile(e)", "committedIndex(e)", "matchesLatestPending(e)")):
            assert source.count(before) == 1
            source = source.replace(before, after)
    target = tmp_path / "instrumented.cjs"
    target.write_text(source, encoding="utf-8")
    runner = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [instrumented,original,replayer,directory]=process.argv.slice(1);
const load=file=>vm.runInNewContext(fs.readFileSync(file,'utf8')+';ur',{require});
const Stream=load(instrumented),Old=load(original),{replay}=require(replayer);
const a={key:'private-a',tag:'p',text:'例子：',linkTargets:['https://private.example/a']};
const b={key:'private-b',tag:'p',text:'private body'};
const cases=[
 ['repeat',[a,b],[a,b,{...a,key:'private-new'}],'block_order_changed'],
 ['reorder',[a,b],[b,a],'block_order_changed'],
 ['rewrite',[a,b],[{...a,text:'changed'},b],'text_changed'],
 ['new-identity',[a,b],[{...a,key:'different-a'},{...b,key:'different-b'}],null],
 ['whitespace',[{...a,text:' '},b],[{...a,text:'\t'},b],'text_changed'],
 ['links',[a,b],[{...a,linkTargets:['https://private.example/b']},b],'link_target_changed'],
 ['overlap',[{...a,sourceStart:0,sourceEnd:10}],[{...b,sourceStart:5,sourceEnd:20}],'source_range_overlap'],
];
for(const [name,committed,observed,reason] of cases){
 const stream=new Stream(),old=new Old();
 stream.committed=committed;old.committed=committed;
 assert(Array.isArray(stream.reconcile(committed)));
 const actual=stream.reconcile(observed),expected=old.reconcile(observed);
 assert.equal(Array.isArray(actual),Array.isArray(expected),name);
 assert.equal(actual.diagnostic?.reason??null,reason,name);
 if(!reason)continue;
 const record={markdownConflict:actual.diagnostic};
 const history=record.markdownConflict.reconciliation;
 assert(history.lastConsistent);assert(history.firstConflict);assert(history.finalConflict.replayable);
 assert.equal(replay(record).reason,reason,name);
 assert.equal(replay(record,'lastConsistent').consistent,true);
 const recorded=history.finalConflict.decisions.filter(x=>x.kind==='committed').map(x=>x.chosen);
 assert.deepEqual(replay(record).choices.map(x=>x.chosen),Array.from(recorded),name);
 if(name==='repeat'){
   const last=history.finalConflict.decisions.at(-1);
   assert.equal(last.alreadySelected,true);assert.equal(last.chosen,0);assert.equal(last.observedIndex,2);
   assert.equal(last.matchedBy,'text_fallback');
   const first=history.firstConflict.sequence;
   const again=stream.reconcile(observed);
   assert.equal(again.diagnostic.reconciliation.firstConflict.sequence,first);
   assert(again.diagnostic.reconciliation.finalConflict.sequence>first);
   fs.writeFileSync(require('node:path').join(directory,'failure.json'),JSON.stringify(record));
 }
 const raw=JSON.stringify(record);
 for(const secret of ['private','例子：','https://'])assert(!raw.includes(secret),secret);
}
// Diagnostic truncation must be explicit and cannot be silently replayed.
const large=new Stream();large.committed=[a,b];
const error=large.reconcile([a,b,...Array.from({length:2001},(_,i)=>({...a,key:'new'+i}))]);
assert.equal(error.diagnostic.reconciliation.finalConflict.replayable,false);
assert.throws(()=>replay({markdownConflict:error.diagnostic}),/截断/);
// Hashing failure preserves the exact upstream error and reports the evidence gap.
const Broken=vm.runInNewContext(fs.readFileSync(instrumented,'utf8')+';ur',
 {require(){throw Error('unavailable')}});
const broken=new Broken();broken.committed=[a,b];
const failure=broken.reconcile([b,a]);assert.equal(failure.diagnostic.reason,'block_order_changed');
assert.equal(failure.diagnostic.detailCaptureFailed,true);
// A conflict is persisted without invoking the terminal browser checkpoint.
const api=vm.runInNewContext(fs.readFileSync(instrumented,'utf8')+
 ';({Stream:ur,bind:codexWebBindReconciliation,open:codexWebJournalOpen,'+
 'page:codexWebJournalBind,close:codexWebJournalClose})',{require,process,performance,console});
const page=new (require('node:events'))(),capture={traceId:'replay-persist',directory};
api.open(capture);api.page(capture,page);
const saved=api.bind(new api.Stream(),page);saved.committed=[a,b];
saved.reconcile([a,b,{...a,key:'new'}]);
const persisted=JSON.parse(fs.readFileSync(require('node:path').join(directory,'reconciliation-live.json')));
assert.equal(replay(persisted).reason,'block_order_changed');api.close(capture);
'''
    replayer = ROOT / "scripts/codex-web-diagnostics/replay.cjs"
    result = subprocess.run(["node", "-e", runner, str(target), str(FIXTURE), str(replayer), str(tmp_path)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    replayed = subprocess.run(["node", str(replayer), str(tmp_path / "failure.json")],
                              capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert replayed.returncode == 0, replayed.stderr
    assert json.loads(replayed.stdout)["reason"] == "block_order_changed"


def test_send_and_completion_evidence_is_bounded_private_and_failure_safe():
    runner = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let now=1000;const page={};
const api=vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8')+
  ';({start:codexWebSendStart,record:codexWebSendRecord,progress:codexWebSendProgress,'+
  'step:codexWebSendStep,'+
  'observe:codexWebObserveSubmission,send:codexWebSendCapture,'+
  'store:codexWebStoreCompletion,completion:codexWebCompletionCapture,'+
  'conflict:codexWebConflictDiagnostic})',
  {require,performance:{now:()=>now},
    je:class extends Error{constructor(message,diagnostic){super(message);this.diagnostic=diagnostic}}});
(async()=>{
  const before={key:'key',tag:'p',text:'link',sourceStart:0,sourceEnd:4,
    linkTargets:['https://private.example/path?a=1']};
  const after={...before,linkTargets:['https://private.example/path?a=2']};
  const conflict=api.conflict.call({committed:[before]},'link_target_changed',after,before,
    {observed:[after],pending:[],previousCommittedIndex:-1});
  assert.equal(conflict.diagnostic.detail.linkCounts.committed,1);
  assert.equal(conflict.diagnostic.detail.schemaVersion,3);
  assert.equal(conflict.diagnostic.detail.linkChanges[0].pathChanged,false);
  assert.equal(conflict.diagnostic.detail.linkChanges[0].queryChanged,true);
  assert(!JSON.stringify(conflict.diagnostic).includes('private.example'));
  api.start(page,'private prompt');now+=7;api.record(page,'press_started');
  assert.equal(await api.step(page,'session_check',async()=>42),42);
  await assert.rejects(api.step(page,'rate_limit_check',async()=>{
    throw Error('private failure');
  }));
  api.step(page,'tool_answer_observation',()=>new Promise(()=>{}));
  assert.equal(api.send(page).milestones.tool_answer_observation_started.count,1);
  assert.equal(api.send(page).milestones.tool_answer_observation_completed,undefined);
  api.progress(page,{revision:1,lastToolBatchRevision:0});
  now+=5;await api.observe(page,async()=>({snapshot:{userTurnCount:1,assistantTurnCount:0,
    composerChars:0,visibleStopButtonCount:1}}));
  now+=5000;await assert.rejects(api.observe(page,async()=>{
    throw Object.assign(Error('private failure'),{name:'ChatGptBrowserObservationTimeoutError'});
  }));
  for(let i=0;i<60;i++)api.record(page,'loop',{count:i});
  const send=api.send(page);assert.equal(send.promptChars,14);
  assert.equal(send.schemaVersion,4);
  assert.equal(send.events.length,40);
  assert.equal(send.milestones.press_started.firstElapsedMs,7);
  assert.equal(send.milestones.session_check_completed.count,1);
  assert.equal(send.milestones.rate_limit_check_failed.count,1);
  assert(send.eventCount>40);
  assert.equal(send.events.at(-1).count,59);
  assert(!JSON.stringify(send).includes('private'));
  api.store(page,JSON.stringify({response:{textChars:12,htmlChars:20,rawAnswer:'secret answer',
    matchedActionCount:0,descriptors:[{tag:'button',role:'button',testId:'conversation-turn-secret',
    classes:['safe-class','not safe'],ancestors:[{tag:'div',testId:'turn-action-controls'}],
    attributeNames:['data-testid','secret value'],withinCurrent:false,withinAssistant:true,
    visible:false,disabled:true,ariaLabel:'复制',title:'Copy',uiAction:true,
    selectorHits:{configured:false,copyAction:false,actionContainer:true},textChars:13}],
    surroundingControls:[{tag:'button',testId:'new-copy-action',withinCurrent:false,
      uiAction:true,ariaLabel:'https://private.example/secret'}]},
    globalActions:{total:1,visible:1},
    globalMatchedControls:[{tag:'button',testId:'copy-turn-action-button',withinCurrent:false}],overlays:[]}));
  const proof=api.completion(page);
  assert.equal(proof.schemaVersion,3);
  assert.equal(proof.nearbyControls[0].testId,'conversation-turn-*');
  assert.equal(proof.nearbyControls[0].classes[1],null);
  assert.equal(proof.nearbyControls[0].ancestors[0].testId,'turn-action-controls');
  assert.equal(proof.nearbyControls[0].attributeNames[1],null);
  assert.equal(proof.nearbyControls[0].ariaLabel,'复制');
  assert.equal(proof.nearbyControls[0].visible,false);
  assert.equal(proof.nearbyControls[0].disabled,true);
  assert.equal(proof.surroundingControls[0].testId,null);
  assert.equal(proof.surroundingControls[0].ariaLabel,null);
  assert.match(proof.surroundingControls[0].ariaLabelFingerprint,/^[0-9a-f]{64}$/);
  assert.equal(proof.globalMatchedControls[0].withinCurrent,false);
  assert.equal(proof.globalActions.total,1);
  assert.match(proof.answerFingerprint,/^[0-9a-f]{64}$/);
  assert(!JSON.stringify(proof).includes('secret'));
  // A moved action no longer matches the configured selector, but its actual UI
  // label, location and parent structure must still survive the failure capture.
  const selector='.turn-action-controls button',assistantSelector='[data-assistant]';
  const make=(tag,attrs={},classes=[],rect={top:100,bottom:200,left:100})=>({
    tagName:tag.toUpperCase(),isConnected:true,disabled:false,classList:classes,
    attributes:Object.keys(attrs).map(name=>({name})),parentElement:null,
    textContent:'',innerText:'',innerHTML:'',
    getAttribute:name=>attrs[name]??null,
    getBoundingClientRect:()=>rect,getClientRects:()=>[rect],
    matches:()=>false,closest:()=>null,contains:()=>false,querySelectorAll:()=>[],
  });
  const current=make('div',{},[],{top:100,bottom:200,left:100});
  current.innerText='secret answer';current.textContent='secret answer';
  const wrapper=make('div',{},['message-row']);
  const moved=make('button',{'aria-label':'新的复制按钮','type':'button'},['new-actions'],
    {top:210,bottom:230,left:110});
  current.parentElement=wrapper;moved.parentElement=wrapper;
  wrapper.contains=node=>node===moved||node===current;
  wrapper.querySelectorAll=()=>[moved];
  const document={querySelectorAll:query=>query===selector?[]:
    query==='button[data-testid="copy-turn-action-button"]'||
    query==='[data-turn-key] .turn-action-controls button'||
    query==='[role="dialog"],[role="alert"],[role="status"]'?[]:[moved]};
  const shape=vm.runInNewContext(process.argv[2],{F:[current],x:selector,
    y:assistantSelector,diagnosticCheckpoint:'response-stalled-60s',document,
    getComputedStyle:()=>({display:'block',visibility:'visible',opacity:'1'}),_:()=>true});
  assert.equal(shape.response.matchedActionCount,0);
  assert.equal(shape.candidateCounts.globalFallbackTotal,1);
  assert.equal(shape.globalFallbackControls[0].ariaLabel,'新的复制按钮');
  api.store(page,JSON.stringify(shape));
  assert.equal(api.completion(page).globalFallbackControls[0].ariaLabel,null);
  assert.match(api.completion(page).globalFallbackControls[0].ariaLabelFingerprint,/^[0-9a-f]{64}$/);
  assert(!JSON.stringify(api.completion(page)).includes('新的复制按钮'));
  assert.equal(api.completion(page).globalFallbackControls[0].nearCurrent,true);
  assert(!JSON.stringify(api.completion(page)).includes('secret answer'));
  const broken=vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8')+
    ';({start:codexWebSendStart,send:codexWebSendCapture,'+
    'store:codexWebStoreCompletion,completion:codexWebCompletionCapture})',
    {require:()=>{throw Error('hash unavailable')},performance:{now:()=>now}});
  const otherPage={};broken.start(otherPage,'private prompt');
  assert.equal(broken.send(otherPage).diagnosticFailureKind,'fingerprint_failed');
  broken.store(otherPage,JSON.stringify({response:{rawAnswer:'secret answer',textChars:13}}));
  assert.equal(broken.completion(otherPage).diagnosticFailureKind,'fingerprint_failed');
  assert(!JSON.stringify(broken.completion(otherPage)).includes('secret answer'));
  console.log('private bounded send/completion evidence passed');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    source = ROOT / "scripts/codex-web-diagnostics/conflict-diagnostic.js"
    result = subprocess.run(["node", "-e", runner, str(source), patch.COMPLETION_SHAPE],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr


def test_package_manifest_apply_repeat_restore_and_mismatch(sample, tmp_path, monkeypatch):
    target, backup, original = sample
    manifest_path = target.parent.parent / "manifest.json"
    manifest_backup = tmp_path / "backup/manifest.original"
    files = [{"path": "app/browser-helper.cjs", "size": len(original), "sha256": patch.digest(original)}]
    manifest = {"schemaVersion": 2, "appVersion": "6.1.2", "files": files}
    bundle = __import__("hashlib").sha256()
    for file in files:
        for field in (file["path"], "\0", str(file["size"]), "\0", file["sha256"], "\0"):
            bundle.update(field.encode())
    manifest["bundleId"] = bundle.hexdigest()
    official = (json.dumps(manifest, indent=2) + "\n").encode()
    manifest_path.write_bytes(official)
    monkeypatch.setattr(patch, "ORIGINAL_MANIFEST_SHA256", patch.digest(official))
    args = (target, backup, manifest_path, manifest_backup)
    assert patch.operate_package("check", *args) == "original"
    assert patch.operate_package("apply", *args) == "applied"
    assert patch.operate_package("apply", *args) == "already_patched"
    assert patch.operate_package("check", *args) == "patched"
    assert backup.read_bytes() == original
    assert manifest_backup.read_bytes() == official
    changed = json.loads(manifest_path.read_text())
    assert changed["files"][0]["sha256"] == patch.digest(target.read_bytes())
    assert changed["files"][0]["size"] == target.stat().st_size
    manifest_path.write_bytes(official)
    with pytest.raises(ValueError, match="状态不一致"):
        patch.operate_package("apply", *args)
    manifest_path.write_bytes(patch.patched_manifest(official, target.read_bytes()))
    assert patch.operate_package("restore", *args) == "restored"
    assert target.read_bytes() == original
    assert manifest_path.read_bytes() == official
