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
