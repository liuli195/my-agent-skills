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
