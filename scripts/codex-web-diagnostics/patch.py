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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "apply", "restore"))
    parser.add_argument("--target", required=True, type=Path, help="明确指定 browser-helper.cjs")
    parser.add_argument("--backup", required=True, type=Path, help="版本目录之外的原始备份位置")
    arguments = parser.parse_args()
    try:
        result = operate(arguments.action, arguments.target, arguments.backup)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps({"status": result, "target": str(arguments.target.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
