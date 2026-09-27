"""Apply/revert a diagnostic-only patch to an explicitly selected 6.1.2 helper."""
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
PATCH_SOURCE = Path(__file__).with_name("conflict-diagnostic.js")
OLD_METHOD = 'changedCommittedBlockError(e,t,r){return new je("ChatGPT changed a completed text block that was already streamed to Codex",{reason:e,observedStart:t.sourceStart,observedEnd:t.sourceEnd,committedStart:r.sourceStart,committedEnd:r.sourceEnd,observedTextChars:t.text.length,committedTextChars:r.text.length})}'
OLD_THROW = 'throw new k(f.message,{status:502,errorType:"server_error",code:"browser_stream_inconsistent",retryable:!1})'
NEW_THROW = '{const diagnosticError=new k(f.message,{status:502,errorType:"server_error",code:"browser_stream_inconsistent",retryable:!1});diagnosticError.diagnostic=f.diagnostic;throw diagnosticError}'
CAPTURE_ANCHOR = 'checkpoint:t,...r!==void 0?{error:ht(r instanceof Error?r.message:String(r))}:{},'


def replacements() -> list[tuple[str, str]]:
    # Read normalized patch text so checkout line endings do not change the patch.
    addition = PATCH_SOURCE.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip() + "\n"
    context = '{observed:e,pending:t,previousCommittedIndex:o}'
    return [
        ('class je extends Error', addition + 'class je extends Error'),
        (OLD_METHOD, 'changedCommittedBlockError(e,t,r,context){return codexWebConflictDiagnostic.call(this,e,t,r,context)}'),
        ('"text_changed",s,h)', '"text_changed",s,h,' + context + ')'),
        ('("link_target_changed",s,h)', '("link_target_changed",s,h,' + context + ')'),
        ('("source_range_overlap",s,r)', '("source_range_overlap",s,r,' + context + ')'),
        (OLD_THROW, NEW_THROW),
        (CAPTURE_ANCHOR, CAPTURE_ANCHOR + '...r?.diagnostic?.detail||r?.diagnostic?.detailCaptureFailed?{markdownConflict:r.diagnostic}:{},'),
    ]


def transform(data: bytes, *, reverse: bool = False) -> bytes:
    text = data.decode("utf-8")
    edits = replacements()
    for old, new in reversed(edits) if reverse else edits:
        before, after = (new, old) if reverse else (old, new)
        if text.count(before) != 1:
            raise ValueError("补丁定位不唯一或文件不兼容；未写入。")
        text = text.replace(before, after, 1)
    return text.encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect(data: bytes) -> tuple[str, bytes]:
    if digest(data) == ORIGINAL_SHA256:
        return "original", data
    try:
        original = transform(data, reverse=True)
    except (ValueError, UnicodeError):
        raise ValueError("文件指纹不匹配：仅支持未经修改的 6.1.2 Windows x64 文件及本补丁。") from None
    if digest(original) != ORIGINAL_SHA256:
        raise ValueError("补丁之外的内容已发生变化；拒绝覆盖。")
    return "patched", original


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
    if package.get("name") != "codex-chatgpt-web" or package.get("version") != "6.1.2":
        raise ValueError("目标软件名称或版本不匹配。")
    if backup.is_relative_to(target.parent.parent):
        raise ValueError("备份必须放在版本目录之外，避免被启动器恢复程序时移除。")
    current = target.read_bytes()
    state, original = inspect(current)
    if backup.exists() and backup.read_bytes() != original:
        raise ValueError("已有备份不匹配；拒绝覆盖备份和目标。")
    if action == "check":
        return state
    if action == "apply":
        patched = transform(original)
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
    if package.get("name") != "codex-chatgpt-web" or package.get("version") != "6.1.2":
        raise ValueError("目标软件名称或版本不匹配。")
    current_helper, current_manifest = target.read_bytes(), manifest_path.read_bytes()
    helper_state, original_helper = inspect(current_helper)
    if digest(current_manifest) == ORIGINAL_MANIFEST_SHA256:
        manifest_state, original_manifest = "original", current_manifest
    elif manifest_backup.is_file() and digest(manifest_backup.read_bytes()) == ORIGINAL_MANIFEST_SHA256:
        original_manifest = manifest_backup.read_bytes()
        manifest_state = "patched" if current_manifest == patched_manifest(original_manifest, transform(original_helper)) else "unknown"
    else:
        raise ValueError("清单不是官方原件或本补丁生成的清单；拒绝覆盖。")
    if manifest_state == "unknown" or helper_state != manifest_state:
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
    next_helper = transform(original_helper) if action == "apply" else original_helper
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
