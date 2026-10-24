from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "plugins" / "pr-flow" / "skills" / "pr-flow" / "scripts" / "pr_flow.py"


def load_pr_flow_module():
    spec = importlib.util.spec_from_file_location("pr_flow_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing_pr_flow_script: {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def invoke_pr_flow(argv: list[str], *, module=None) -> subprocess.CompletedProcess[str]:
    if module is None:
        module = load_pr_flow_module()
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        returncode = int(module.main(argv))
    return subprocess.CompletedProcess(
        args=[str(SCRIPT), *argv],
        returncode=returncode,
        stdout=stdout.getvalue(),
        stderr=stderr.getvalue(),
    )


def fixed_text_file_io(monkeypatch, *, root: Path, files: dict[Path, str | None], directories: set[Path]):
    """Bind only explicitly declared text-file leaves; never emulate a directory tree.

    Source reads outside root retain their real read-only implementation. Unknown
    in-memory reads and every undeclared write fail instead of reaching the disk.
    The caller declares all names, including output files, before invoking main.
    """
    original = {name: getattr(Path, name) for name in (
        "read_text", "write_text", "read_bytes", "write_bytes", "exists", "is_file", "is_dir", "mkdir", "unlink", "glob",
    )}
    present_directories = {root}

    def inside(path):
        return path == root or root in path.parents

    def declared_file(path):
        if path not in files:
            raise AssertionError(f"undeclared_text_file: {path}")

    def read_text(path, *args, **kwargs):
        if not inside(path):
            return original["read_text"](path, *args, **kwargs)
        declared_file(path)
        if files[path] is None:
            raise FileNotFoundError(path)
        return files[path]

    def write_text(path, text, *args, **kwargs):
        declared_file(path)
        files[path] = text
        return len(text)

    def read_bytes(path):
        if not inside(path):
            return original["read_bytes"](path)
        return read_text(path).encode("utf-8")

    def write_bytes(path, data):
        write_text(path, bytes(data).decode("utf-8"))
        return len(data)

    def exists(path):
        if not inside(path):
            return original["exists"](path)
        if path in directories:
            return path in present_directories
        declared_file(path)
        return files[path] is not None

    def is_file(path):
        if not inside(path):
            return original["is_file"](path)
        if path in directories:
            return False
        declared_file(path)
        return files[path] is not None

    def is_dir(path):
        if not inside(path):
            return original["is_dir"](path)
        if path in files:
            return False
        if path not in directories:
            raise AssertionError(f"undeclared_directory: {path}")
        return path in present_directories

    def mkdir(path, mode=0o777, parents=False, exist_ok=False):
        if path not in directories:
            raise AssertionError(f"undeclared_directory_write: {path}")
        if path in present_directories and not exist_ok:
            raise FileExistsError(path)
        if not parents and path.parent not in present_directories:
            raise FileNotFoundError(path.parent)
        present_directories.add(path)
        if parents:
            present_directories.update(parent for parent in path.parents if parent in directories)

    def unlink(path, missing_ok=False):
        declared_file(path)
        if files[path] is None and not missing_ok:
            raise FileNotFoundError(path)
        files[path] = None

    def glob(path, pattern, *args, **kwargs):
        if not inside(path):
            return original["glob"](path, pattern, *args, **kwargs)
        if path not in directories or pattern not in {"*.json", "hotfix-*.json"}:
            raise AssertionError(f"undeclared_output_listing: {path}/{pattern}")
        return iter(file for file, text in files.items() if text is not None and file.parent == path and file.match(pattern))

    for name, replacement in locals().copy().items():
        if name in original:
            monkeypatch.setattr(Path, name, replacement)
    return files
