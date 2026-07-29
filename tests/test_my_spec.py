from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "my-spec"
SPEC_OPS = PLUGIN_ROOT / "python" / "spec_ops.py"
SKILL_NAMES = ("my-spec", "my-spec-add", "my-spec-review", "my-spec-audit")


def run_python(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *(str(arg) for arg in args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def requirement(title: str, behavior: str, scenario: str = "正常流程") -> str:
    return f"""### Requirement: {title}

系统 MUST {behavior}。

#### Scenario: {scenario}

- **WHEN** 用户执行操作
- **THEN** 系统返回结果
"""


def main_spec(capability: str, *requirements: str) -> str:
    return f"""# {capability}

## Purpose

描述 {capability} 的外部行为。

## Requirements

{"\n".join(requirements)}"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def ready_state(cli: Path, root: Path, command: str = "add") -> Path:
    work = root / ".local" / "spec-work"
    conflicts = root / "no-conflicts.json"
    write(conflicts, "[]")
    initialized = run_python(
        cli, "state-init", work, command, "specs-fingerprint", "input-fingerprint"
    )
    assert initialized.returncode == 0, initialized.stderr
    stored = run_python(
        cli,
        "state-set-conflicts",
        work,
        conflicts,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert stored.returncode == 0, stored.stderr
    return work


def apply_ready(
    cli: Path,
    specs: Path,
    delta: Path,
    output: Path,
    work: Path,
) -> subprocess.CompletedProcess[str]:
    return run_python(
        cli,
        "apply-delta",
        specs,
        delta,
        output,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )


def run_confirmed_workflow(
    cli: Path,
    specs: Path,
    delta: Path,
    preview: Path,
    *expected_diff: str,
) -> str:
    work = ready_state(cli, preview.parent)
    validated = run_python(cli, "validate-delta", delta, specs)
    assert validated.returncode == 0, validated.stderr
    generated = run_python(
        cli,
        "apply-delta",
        specs,
        delta,
        preview,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert generated.returncode == 0, generated.stderr
    assert run_python(cli, "validate-main", preview).returncode == 0
    diff = run_python(cli, "diff", specs, preview)
    assert diff.returncode == 0, diff.stderr
    for fragment in expected_diff:
        assert fragment in diff.stdout
    applied = run_python(
        cli,
        "apply-delta",
        specs,
        delta,
        specs,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert applied.returncode == 0, applied.stderr
    assert run_python(cli, "validate-main", specs).returncode == 0
    assert run_python(cli, "diff", specs, preview).stdout == ""
    return diff.stdout


def install_packed_myspec(tmp_path: Path) -> tuple[Path, Path]:
    npm = shutil.which("npm")
    assert npm is not None
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    packed = subprocess.run(
        [npm, "pack", "--json", "--pack-destination", str(package_dir)],
        cwd=PLUGIN_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert packed.returncode == 0, packed.stderr
    package = json.loads(packed.stdout)[0]
    assert package["name"] == "@liuli195/myspec"

    prefix = tmp_path / "npm-prefix"
    installed = subprocess.run(
        [
            npm,
            "install",
            "--global",
            "--prefix",
            str(prefix),
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            str(package_dir / package["filename"]),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    executable = prefix / ("myspec.cmd" if sys.platform == "win32" else "bin/myspec")
    assert executable.is_file()
    npm_root = subprocess.run(
        [npm, "root", "--global", "--prefix", str(prefix)],
        text=True,
        capture_output=True,
        check=True,
    )
    return executable, Path(npm_root.stdout.strip()) / "@liuli195" / "myspec"


def run_cli(executable: Path, *args: object, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(executable), *(str(arg) for arg in args)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def windows_py_launcher() -> Path:
    candidates = (
        Path(sys.executable).parent.parent / "Launcher" / "py.exe",
        Path(os.environ.get("SystemRoot", "C:/Windows")) / "py.exe",
        Path(shutil.which("py") or ""),
    )
    launcher = next(
        (path for path in candidates if path.is_file() and "WindowsApps" not in path.parts),
        None,
    )
    assert launcher is not None
    return launcher


def run_launcher_selection(
    executable: Path,
    root: Path,
    versions: dict[str, str],
    override_version: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[Path], dict[str, Path]]:
    candidates = root / "candidates"
    candidates.mkdir(parents=True)
    paths: dict[str, Path] = {}
    reported_versions: dict[str, str] = {}
    for name, version in versions.items():
        if name == "py":
            source = windows_py_launcher()
        else:
            source = sys.executable
        path = candidates / (f"{name}.exe" if sys.platform == "win32" else name)
        shutil.copy2(source, path)
        paths[name] = path.resolve()
        if version == "3.11":
            reported_versions[os.path.normcase(str(paths[name]))] = version

    env = {
        **os.environ,
        "PATH": os.pathsep.join(
            (
                str(candidates),
                str(Path(shutil.which("node") or "").parent),
                str(Path(sys.executable).parent),
            )
        ),
        "PYTHONPATH": str(root),
        "MYSPEC_TEST_MARKER": str(root / "selected.txt"),
    }
    env.pop("MYSPEC_PYTHON", None)
    if override_version is not None:
        override = root / ("override.exe" if sys.platform == "win32" else "override")
        shutil.copy2(sys.executable, override)
        env["MYSPEC_PYTHON"] = str(override)
        paths["MYSPEC_PYTHON"] = override.resolve()
        if override_version == "3.11":
            reported_versions[os.path.normcase(str(paths["MYSPEC_PYTHON"]))] = override_version
    if sys.platform == "win32" and versions.get("py") == "3.11":
        reported_versions[os.path.normcase(str(Path(sys.executable).resolve()))] = "3.11"
    env["MYSPEC_TEST_VERSIONS"] = json.dumps(reported_versions)
    write(
        root / "sitecustomize.py",
        """import json
import os
import sys
from pathlib import Path

executable = Path(sys.executable).resolve()
with Path(os.environ["MYSPEC_TEST_MARKER"]).open("a", encoding="utf-8") as marker:
    marker.write(str(executable) + "\\n")
version = json.loads(os.environ["MYSPEC_TEST_VERSIONS"]).get(os.path.normcase(str(executable)))
if version:
    major, minor = map(int, version.split("."))
    sys.version_info = type("VersionInfo", (), {"major": major, "minor": minor})()
""",
    )
    result = run_cli(executable, "--help", env=env)
    marker = Path(env["MYSPEC_TEST_MARKER"])
    observed = (
        [Path(line) for line in marker.read_text(encoding="utf-8").splitlines()]
        if marker.exists()
        else []
    )
    return result, observed, paths


def test_packed_myspec_installs_a_working_cli_with_agent_resources(tmp_path: Path) -> None:
    executable, installed_package = install_packed_myspec(tmp_path)
    path_candidates = {"python3.12": "3.12", "python3": "3.12", "python": "3.12"}
    if sys.platform == "win32":
        path_candidates["py"] = "3.12"

    override, observed, paths = run_launcher_selection(
        executable,
        tmp_path / "override-case",
        path_candidates,
        override_version="3.12",
    )
    assert override.returncode == 0, override.stderr
    assert observed[-1] == paths["MYSPEC_PYTHON"]

    cases = [
        ({**path_candidates}, "python3.12"),
        ({**path_candidates, "python3.12": "3.11"}, "python3"),
        ({**path_candidates, "python3.12": "3.11", "python3": "3.11"}, "python"),
    ]
    if sys.platform == "win32":
        cases.append(({name: "3.11" for name in path_candidates} | {"py": "3.12"}, "py"))
    for index, (versions, expected) in enumerate(cases):
        result, observed, paths = run_launcher_selection(
            executable,
            tmp_path / f"priority-case-{index}",
            versions,
            override_version="3.11" if index == 0 else None,
        )
        assert result.returncode == 0, result.stderr
        if expected == "py":
            assert observed[-1] not in paths.values()
        else:
            assert observed[-1] == paths[expected]

    ineligible_versions = {name: "3.11" for name in path_candidates}
    ineligible, _, _ = run_launcher_selection(
        executable,
        tmp_path / "ineligible-case",
        ineligible_versions,
        override_version="3.11",
    )
    assert ineligible.returncode != 0
    assert "error: Python 3.12 or newer is required" in ineligible.stderr
    assert ineligible.stderr.count("(3.11)") == len(ineligible_versions) + 1

    help_result = run_cli(executable, "--help")
    assert help_result.returncode == 0
    assert help_result.stdout.startswith("usage: myspec ")
    for command in (
        "state-init",
        "state-set-conflicts",
        "state-current",
        "state-decide",
        "state-status",
        "validate-main",
        "validate-delta",
        "apply-delta",
        "diff",
    ):
        assert command in help_result.stdout

    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    work = tmp_path / "work"
    conflicts_file = tmp_path / "conflicts.json"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    write(
        delta / "accounts" / "spec.md",
        """## ADDED Requirements

### Requirement: 注销

系统 MUST 允许用户注销。

#### Scenario: 主动注销

- **WHEN** 用户选择注销
- **THEN** 系统结束会话
""",
    )
    conflict = {
        "id": "conflict-1",
        "candidate": "新增注销",
        "evidence": ["accounts/spec.md:1"],
        "reason": "需要确认",
        "recommendation": "接受",
    }
    write(conflicts_file, json.dumps([conflict], ensure_ascii=False))

    for command in (
        run_cli(executable, "validate-main", specs),
        run_cli(executable, "validate-delta", delta, specs),
        run_cli(executable, "state-init", work, "add", "specs-fingerprint", "input-fingerprint"),
    ):
        assert command.returncode == 0, command.stderr
        assert command.stdout == ""
        assert command.stderr == ""

    stored = run_cli(
        executable,
        "state-set-conflicts",
        work,
        conflicts_file,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert stored.returncode == 0, stored.stderr
    assert json.loads(stored.stdout) == {"status": "WAITING_DECISION", "total": 1, "remaining": 1}
    current = run_cli(executable, "state-current", work, "specs-fingerprint", "input-fingerprint")
    assert current.returncode == 0, current.stderr
    assert json.loads(current.stdout) == {"index": 0, "total": 1, "conflict": conflict}

    wrong_decision = run_cli(
        executable,
        "state-decide",
        work,
        "wrong-conflict",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert wrong_decision.returncode == 1
    assert "error: unexpected_conflict_id: expected_conflict-1: wrong-conflict" in wrong_decision.stderr
    decided = run_cli(
        executable,
        "state-decide",
        work,
        "conflict-1",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert decided.returncode == 0, decided.stderr
    expected_ready = {"status": "READY_TO_APPLY", "total": 1, "decided": 1, "remaining": 0}
    assert json.loads(decided.stdout) == expected_ready
    status = run_cli(executable, "state-status", work, "specs-fingerprint", "input-fingerprint")
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout) == expected_ready

    applied = run_cli(
        executable,
        "apply-delta",
        specs,
        delta,
        preview,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert applied.returncode == 0, applied.stderr
    assert applied.stdout == ""
    assert run_cli(executable, "validate-main", preview).returncode == 0
    assert "### Requirement: 注销" in (preview / "accounts" / "spec.md").read_text(encoding="utf-8")
    diff = run_cli(executable, "diff", specs, preview)
    assert diff.returncode == 0, diff.stderr
    assert "+### Requirement: 注销" in diff.stdout

    final_apply = run_cli(
        executable,
        "apply-delta",
        specs,
        delta,
        specs,
        work,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert final_apply.returncode == 0, final_apply.stderr
    assert final_apply.stdout == ""
    assert run_cli(executable, "validate-main", specs).returncode == 0
    assert run_cli(executable, "diff", specs, preview).stdout == ""
    assert (specs / "accounts" / "spec.md").read_bytes() == (
        preview / "accounts" / "spec.md"
    ).read_bytes()
    assert not (work / "current").exists()
    assert not (work / "lock").exists()
    assert not work.exists()
    assert not any(path.name.startswith(".my-spec-") for path in specs.parent.iterdir())

    write(
        specs / "accounts" / "spec.md",
        main_spec("Accounts", requirement("登录", "允许登录")).replace("MUST", "必须"),
    )
    invalid = run_cli(executable, "validate-main", specs)
    assert invalid.returncode == 1
    assert "error: missing_must_or_shall: 登录" in invalid.stderr
    assert "Traceback" not in invalid.stderr
    missing_argument = run_cli(executable, "state-init", work)
    assert missing_argument.returncode == 2
    assert "usage: myspec state-init" in missing_argument.stderr

    node = shutil.which("node")
    assert node is not None
    no_python = run_cli(
        executable,
        "validate-main",
        specs,
        env={**os.environ, "PATH": str(Path(node).parent), "MYSPEC_PYTHON": "not-a-python"},
    )
    assert no_python.returncode != 0
    assert "error: Python 3.12 or newer is required" in no_python.stderr
    assert (
        "checked not-a-python (unavailable), python3.12 (unavailable), "
        "python3 (unavailable), python (unavailable)"
    ) in no_python.stderr

    assert {path.name for path in (installed_package / "skills").iterdir()} == set(SKILL_NAMES)
    assert (installed_package / ".claude-plugin" / "plugin.json").is_file()
    assert (installed_package / ".codex-plugin" / "plugin.json").is_file()
    assert [path.relative_to(installed_package).as_posix() for path in installed_package.rglob("spec_ops.py")] == [
        "python/spec_ops.py",
        "skills/my-spec/scripts/spec_ops.py",
    ]


def test_myspec_launcher_forwards_sigterm_to_python(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("Windows cannot deliver a catchable SIGTERM to another process")
    executable, installed_package = install_packed_myspec(tmp_path)
    marker = tmp_path / "signal.txt"
    ready = tmp_path / "ready.txt"
    (installed_package / "python" / "spec_ops.py").write_text(
        """import os
import signal
import sys
import time
from pathlib import Path

marker = Path(sys.argv[1])
ready = Path(sys.argv[2])
parent = os.getppid()

def stop(signum, _frame):
    marker.write_text(str(signum), encoding="utf-8")
    raise SystemExit(0)

signal.signal(signal.SIGTERM, stop)
ready.write_text("ready", encoding="utf-8")
while os.getppid() == parent:
    time.sleep(0.01)
""",
        encoding="utf-8",
    )
    process = subprocess.Popen(
        [str(executable), str(marker), str(ready)],
        env={**os.environ, "MYSPEC_PYTHON": sys.executable},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 10
    while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert ready.exists(), "Python child did not start"

    process.send_signal(signal.SIGTERM)
    assert process.wait(timeout=10) == 0
    assert marker.read_text(encoding="utf-8") == str(signal.SIGTERM)


def test_spec_ops_cli_validates_applies_all_delta_operations_and_diffs(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    write(
        specs / "accounts" / "spec.md",
        main_spec(
            "Accounts",
            requirement("旧登录", "允许登录"),
            requirement("旧导出", "允许导出"),
            requirement("个人资料", "显示姓名"),
        ),
    )
    write(
        delta / "accounts" / "spec.md",
        """# Accounts

## Purpose

描述 Accounts 的外部行为。

## RENAMED Requirements

FROM: 旧登录
TO: 密码登录

## REMOVED Requirements

### Requirement: 旧导出

## MODIFIED Requirements

### Requirement: 个人资料

系统 SHALL 显示姓名和头像。

#### Scenario: 查看资料

- **WHEN** 用户打开个人资料
- **THEN** 系统显示姓名和头像

## ADDED Requirements

### Requirement: 注销

系统 MUST 允许用户注销。

#### Scenario: 主动注销

- **WHEN** 用户选择注销
- **THEN** 系统结束会话
""",
    )

    work = ready_state(SPEC_OPS, tmp_path / "state")
    assert run_python(SPEC_OPS, "validate-main", specs).returncode == 0
    assert run_python(SPEC_OPS, "validate-delta", delta, specs).returncode == 0
    applied = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert applied.returncode == 0, applied.stderr
    assert run_python(SPEC_OPS, "validate-main", preview).returncode == 0

    merged = (preview / "accounts" / "spec.md").read_text(encoding="utf-8")
    assert "### Requirement: 密码登录" in merged
    assert "### Requirement: 旧登录" not in merged
    assert "### Requirement: 旧导出" not in merged
    assert "系统 SHALL 显示姓名和头像。" in merged
    assert "### Requirement: 注销" in merged

    diff = run_python(SPEC_OPS, "diff", specs, preview)
    assert diff.returncode == 0
    assert "-### Requirement: 旧登录" in diff.stdout
    assert "+### Requirement: 密码登录" in diff.stdout
    assert "旧导出" in diff.stdout
    assert "注销" in diff.stdout

    first_apply = apply_ready(SPEC_OPS, specs, delta, specs, work)
    assert first_apply.returncode == 0, first_apply.stderr
    before_repeat = (specs / "accounts" / "spec.md").read_bytes()
    repeated_validation = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert repeated_validation.returncode == 0, repeated_validation.stderr
    repeated_work = ready_state(SPEC_OPS, tmp_path / "repeated-state")
    repeated_apply = apply_ready(SPEC_OPS, specs, delta, specs, repeated_work)
    assert repeated_apply.returncode == 0, repeated_apply.stderr
    assert (specs / "accounts" / "spec.md").read_bytes() == before_repeat


def test_spec_ops_cli_rejects_invalid_specs_and_delta_references(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    write(
        specs / "accounts" / "spec.md",
        main_spec("Accounts", requirement("登录", "允许登录").replace("MUST", "必须")),
    )

    invalid_main = run_python(SPEC_OPS, "validate-main", specs)
    assert invalid_main.returncode != 0
    assert "missing_must_or_shall: 登录" in invalid_main.stderr
    assert "Traceback" not in invalid_main.stderr

    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    write(
        delta / "accounts" / "spec.md",
        """## MODIFIED Requirements

### Requirement: 不存在的需求

系统 MUST 返回结果。

#### Scenario: 正常流程

- **WHEN** 用户执行操作
- **THEN** 系统返回结果
""",
    )
    invalid_delta = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert invalid_delta.returncode != 0
    assert "modified_source_missing: 不存在的需求" in invalid_delta.stderr
    assert "Traceback" not in invalid_delta.stderr


def test_spec_ops_cli_persists_complete_conflicts_and_resumes_in_a_new_process(
    tmp_path: Path,
) -> None:
    work = tmp_path / ".local" / "spec-work"
    conflicts_file = tmp_path / "conflicts.json"
    conflicts = [
        {
            "id": f"conflict-{index:02d}",
            "candidate": f"候选 {index}",
            "evidence": [f"spec.md:{index}"],
            "reason": "语义冲突",
            "recommendation": "采用建议",
        }
        for index in range(1, 14)
    ]
    write(conflicts_file, json.dumps(conflicts, ensure_ascii=False))

    initialized = run_python(
        SPEC_OPS,
        "state-init",
        work,
        "review",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert initialized.returncode == 0, initialized.stderr
    stored = run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        conflicts_file,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert stored.returncode == 0, stored.stderr
    assert json.loads(stored.stdout) == {"status": "WAITING_DECISION", "total": 13, "remaining": 13}

    first = json.loads(
        run_python(
            SPEC_OPS, "state-current", work, "specs-fingerprint", "input-fingerprint"
        ).stdout
    )
    assert first["index"] == 0
    assert first["total"] == 13
    assert first["conflict"] == conflicts[0]

    decided = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-01",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert decided.returncode == 0, decided.stderr
    second = json.loads(
        run_python(
            SPEC_OPS, "state-current", work, "specs-fingerprint", "input-fingerprint"
        ).stdout
    )
    assert second["index"] == 1
    assert second["total"] == 13
    assert second["conflict"] == conflicts[1]
    assert json.loads(
        run_python(SPEC_OPS, "state-status", work, "specs-fingerprint", "input-fingerprint").stdout
    ) == {
        "status": "WAITING_DECISION",
        "total": 13,
        "decided": 1,
        "remaining": 12,
    }


def test_spec_ops_cli_rejects_incomplete_or_out_of_order_conflict_state(tmp_path: Path) -> None:
    work = tmp_path / ".local" / "spec-work"
    stale_delta = work / "current" / "delta" / "stale" / "spec.md"
    write(stale_delta, "stale")
    assert run_python(
        SPEC_OPS, "state-init", work, "audit", "specs-fingerprint", "input-fingerprint"
    ).returncode == 0
    assert not stale_delta.exists()

    count_only = tmp_path / "count-only.json"
    write(count_only, '{"count": 13}')
    incomplete = run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        count_only,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert incomplete.returncode != 0
    assert "conflicts_must_be_array" in incomplete.stderr

    duplicate_file = tmp_path / "duplicates.json"
    duplicate = {
        "id": "same",
        "candidate": "候选",
        "evidence": ["spec.md:1"],
        "reason": "冲突",
        "recommendation": "采用建议",
    }
    write(duplicate_file, json.dumps([duplicate, duplicate], ensure_ascii=False))
    duplicates = run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        duplicate_file,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert duplicates.returncode != 0
    assert "duplicate_conflict_id: same" in duplicates.stderr

    missing_evidence_file = tmp_path / "missing-evidence.json"
    write(
        missing_evidence_file,
        json.dumps([{**duplicate, "id": "missing", "evidence": []}], ensure_ascii=False),
    )
    missing = run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        missing_evidence_file,
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert missing.returncode != 0
    assert "invalid_conflict_field: missing: evidence" in missing.stderr

    premature = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "same",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert premature.returncode != 0
    assert "invalid_state: expected_WAITING_DECISION" in premature.stderr

    valid_file = tmp_path / "valid.json"
    write(valid_file, json.dumps([duplicate], ensure_ascii=False))
    assert run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        valid_file,
        "specs-fingerprint",
        "input-fingerprint",
    ).returncode == 0
    stale = run_python(
        SPEC_OPS, "state-current", work, "changed-specs", "input-fingerprint"
    )
    assert stale.returncode != 0
    assert "specs_fingerprint_changed" in stale.stderr

    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    delta.mkdir()
    blocked = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert blocked.returncode != 0
    assert "invalid_state: expected_READY_TO_APPLY" in blocked.stderr

    state_path = work / "current" / "state.json"
    inconsistent = json.loads(state_path.read_text(encoding="utf-8"))
    inconsistent["status"] = "READY_TO_APPLY"
    state_path.write_text(json.dumps(inconsistent), encoding="utf-8")
    tampered = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert tampered.returncode != 0
    assert "invalid_state_document" in tampered.stderr


def test_spec_ops_cli_records_each_supported_conflict_decision(tmp_path: Path) -> None:
    work = tmp_path / ".local" / "spec-work"
    conflicts_file = tmp_path / "conflicts.json"
    conflicts = [
        {
            "id": f"conflict-{index}",
            "candidate": f"候选 {index}",
            "evidence": [f"spec.md:{index}"],
            "reason": "需要决定",
            "recommendation": "采用建议",
        }
        for index in range(4)
    ]
    write(conflicts_file, json.dumps(conflicts, ensure_ascii=False))
    assert run_python(
        SPEC_OPS, "state-init", work, "add", "specs-fingerprint", "input-fingerprint"
    ).returncode == 0
    assert run_python(
        SPEC_OPS,
        "state-set-conflicts",
        work,
        conflicts_file,
        "specs-fingerprint",
        "input-fingerprint",
    ).returncode == 0

    assert run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-0",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    ).returncode == 0
    repeated = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-0",
        "accept",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert repeated.returncode != 0
    assert "unexpected_conflict_id: expected_conflict-1: conflict-0" in repeated.stderr
    assert run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-1",
        "ignore",
        "specs-fingerprint",
        "input-fingerprint",
    ).returncode == 0
    modified = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-2",
        "accept-modified",
        "specs-fingerprint",
        "input-fingerprint",
        "--modified-content",
        "修改后的完整候选",
    )
    assert modified.returncode == 0, modified.stderr
    final = run_python(
        SPEC_OPS,
        "state-decide",
        work,
        "conflict-3",
        "defer",
        "specs-fingerprint",
        "input-fingerprint",
    )
    assert final.returncode == 0, final.stderr
    assert json.loads(final.stdout) == {
        "status": "READY_TO_APPLY",
        "total": 4,
        "decided": 4,
        "remaining": 0,
    }
    state = json.loads((work / "current" / "state.json").read_text(encoding="utf-8"))
    assert [item["decision"] for item in state["decisions"]] == [
        "accept",
        "ignore",
        "accept-modified",
        "defer",
    ]
    assert state["decisions"][2]["modifiedContent"] == "修改后的完整候选"


def test_spec_ops_cli_initializes_a_new_capability_from_an_empty_spec_library(tmp_path: Path) -> None:
    specs = tmp_path / "missing-specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    write(
        delta / "notifications" / "spec.md",
        """# Notifications

## Purpose

描述通知的外部行为。

## ADDED Requirements

### Requirement: 接收通知

系统 MUST 向订阅用户发送通知。

#### Scenario: 新消息

- **WHEN** 新消息到达
- **THEN** 系统向订阅用户发送通知
""",
    )

    work = ready_state(SPEC_OPS, tmp_path / "state")
    validated = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert validated.returncode == 0, validated.stderr
    applied = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert applied.returncode == 0, applied.stderr
    assert run_python(SPEC_OPS, "validate-main", preview).returncode == 0
    assert "### Requirement: 接收通知" in (preview / "notifications" / "spec.md").read_text(encoding="utf-8")


def test_spec_ops_preview_auto_merges_identical_duplicate_requirements_but_main_validation_stays_strict(
    tmp_path: Path,
) -> None:
    specs = tmp_path / "specs"
    delta = tmp_path / "delta"
    preview = tmp_path / "preview"
    duplicate = requirement("登录", "允许用户登录")
    write(specs / "accounts" / "spec.md", main_spec("Accounts", duplicate))
    write(specs / "sessions" / "spec.md", main_spec("Sessions", duplicate))
    delta.mkdir()

    strict = run_python(SPEC_OPS, "validate-main", specs)
    assert strict.returncode != 0
    assert "duplicate_requirement_global: 登录" in strict.stderr

    work = ready_state(SPEC_OPS, tmp_path / "state", "review")
    merged = apply_ready(SPEC_OPS, specs, delta, preview, work)
    assert merged.returncode == 0, merged.stderr
    assert run_python(SPEC_OPS, "validate-main", preview).returncode == 0
    assert (preview / "accounts" / "spec.md").read_text(encoding="utf-8").count(
        "### Requirement: 登录"
    ) == 1
    diff = run_python(SPEC_OPS, "diff", specs, preview)
    assert diff.returncode == 0
    assert "-### Requirement: 登录" in diff.stdout


def test_skill_entries_route_add_review_and_audit_with_safe_boundaries() -> None:
    skill = (PLUGIN_ROOT / "skills" / "my-spec" / "SKILL.md").read_text(encoding="utf-8")
    assert "name: my-spec" in skill
    assert "my-spec-add" in skill and "references/add-document.md" in skill
    assert "my-spec-review" in skill and "references/review.md" in skill
    assert "my-spec-audit" in skill and "references/audit.md" in skill

    for name in SKILL_NAMES:
        entry = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert f"name: {name}" in entry
    for name in SKILL_NAMES[1:]:
        entry = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "../my-spec/SKILL.md" in entry
        assert "../my-spec/scripts/spec_ops.py" in entry

    legacy_cli = PLUGIN_ROOT / "skills" / "my-spec" / "scripts" / "spec_ops.py"
    legacy_help = run_python(legacy_cli, "--help")
    assert legacy_help.returncode == 0, legacy_help.stderr
    assert legacy_help.stdout.startswith("usage: myspec ")

    add = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "add-document.md").read_text(encoding="utf-8")
    review = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "review.md").read_text(encoding="utf-8")
    audit = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "audit.md").read_text(encoding="utf-8")
    rules = (PLUGIN_ROOT / "skills" / "my-spec" / "references" / "myspec-rules.md").read_text(encoding="utf-8")
    for procedure in (add, review, audit):
        assert "一次只展示一条" in procedure
        assert "完整差异" in procedure
        assert "最终确认" in procedure
        assert "spec_ops.py" in procedure
    assert "只读取 `myspec/specs/`" in review
    assert "不得读取仓库其他文件" in review
    assert "git ls-files --cached --others --exclude-standard" in audit
    assert ".local/spec-work/" in skill and ".local/spec-work/" in audit and ".local/spec-work/" in rules
    assert ".spec-work/" not in skill + audit + rules
    assert "Agent" in add and "相关证据" in add
    assert "指定文档" not in add
    for procedure in (add, review, audit):
        assert "state-set-conflicts" in procedure
        assert "首次展示" in procedure
        assert "禁止重新" in procedure


def test_plugin_uses_host_native_skill_paths_without_custom_pi_routing() -> None:
    assert not (PLUGIN_ROOT / "scripts").exists()
    assert not (PLUGIN_ROOT / "extensions").exists()

    package = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["name"] == "@liuli195/myspec"
    assert package["bin"] == {"myspec": "./bin/myspec.js"}
    assert package["publishConfig"] == {"access": "public"}
    assert package["pi"] == {"skills": ["./skills"]}
    assert "peerDependencies" not in package
    assert "dependencies" not in package


def test_spec_add_deterministic_post_analysis_flow_previews_diffs_and_applies(
    tmp_path: Path,
) -> None:
    cli = SPEC_OPS
    specs = tmp_path / "add" / "specs"
    delta = tmp_path / "add" / "delta"
    preview = tmp_path / "add" / "preview"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许用户登录")))
    write(
        delta / "accounts" / "spec.md",
        """## ADDED Requirements

### Requirement: 注销

系统 MUST 允许用户注销。

#### Scenario: 主动注销

- **WHEN** 用户选择注销
- **THEN** 系统结束会话
""",
    )

    run_confirmed_workflow(cli, specs, delta, preview, "+### Requirement: 注销")
    assert "### Requirement: 注销" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")


def test_spec_review_deterministic_duplicate_flow_previews_diffs_and_applies(
    tmp_path: Path,
) -> None:
    cli = SPEC_OPS
    specs = tmp_path / "review" / "specs"
    delta = tmp_path / "review" / "delta"
    preview = tmp_path / "review" / "preview"
    duplicate = requirement("登录", "允许用户登录")
    write(specs / "accounts" / "spec.md", main_spec("Accounts", duplicate, duplicate))
    delta.mkdir(parents=True)

    run_confirmed_workflow(cli, specs, delta, preview, "-### Requirement: 登录")
    assert (specs / "accounts" / "spec.md").read_text(encoding="utf-8").count(
        "### Requirement: 登录"
    ) == 1


def test_spec_audit_deterministic_post_analysis_flow_previews_diffs_and_applies(
    tmp_path: Path,
) -> None:
    cli = SPEC_OPS
    specs = tmp_path / "audit" / "missing-specs"
    delta = tmp_path / "audit" / "delta"
    preview = tmp_path / "audit" / "preview"
    write(
        delta / "notifications" / "spec.md",
        """# Notifications

## Purpose

描述通知的外部行为。

## ADDED Requirements

### Requirement: 接收通知

系统 MUST 向订阅用户发送通知。

#### Scenario: 新消息

- **WHEN** 新消息到达
- **THEN** 系统发送通知
""",
    )

    run_confirmed_workflow(cli, specs, delta, preview, "+### Requirement: 接收通知")
    assert (specs / "notifications" / "spec.md").is_file()


def test_my_spec_plugin_is_discoverable_by_pi_claude_and_codex() -> None:
    package_version = json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    spec = (REPO_ROOT / "myspec" / "specs" / "my-spec" / "spec.md").read_text(encoding="utf-8")
    assert "/skill:my-spec-add" in spec
    assert "/my-spec:my-spec-add" in spec
    assert "$my-spec-add" in spec
    for host in (".claude-plugin", ".codex-plugin"):
        manifest = json.loads((PLUGIN_ROOT / host / "plugin.json").read_text(encoding="utf-8"))
        assert manifest["name"] == "my-spec"
        assert manifest["version"] == package_version
        assert manifest["skills"] == "./skills"

    claude_marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    codex_marketplace = json.loads((REPO_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert any(plugin["name"] == "my-spec" for plugin in claude_marketplace["plugins"])
    assert any(plugin["name"] == "my-spec" for plugin in codex_marketplace["plugins"])


def test_apply_delta_can_atomically_replace_main_after_final_confirmation(tmp_path: Path) -> None:
    specs = tmp_path / "myspec" / "specs"
    delta = tmp_path / "delta"
    write(specs / "accounts" / "spec.md", main_spec("Accounts", requirement("登录", "允许登录")))
    write(
        delta / "accounts" / "spec.md",
        """## MODIFIED Requirements

### Requirement: 登录

系统 MUST 允许密码登录。

#### Scenario: 密码正确

- **WHEN** 用户提交正确密码
- **THEN** 系统创建会话
""",
    )

    work = ready_state(SPEC_OPS, tmp_path / "state")
    applied = apply_ready(SPEC_OPS, specs, delta, specs, work)
    assert applied.returncode == 0, applied.stderr
    assert "系统 MUST 允许密码登录。" in (specs / "accounts" / "spec.md").read_text(encoding="utf-8")
    assert not any(path.name.startswith(".my-spec-") for path in specs.parent.iterdir())
    assert not work.exists()
    assert run_python(SPEC_OPS, "validate-main", specs).returncode == 0

    before = (specs / "accounts" / "spec.md").read_bytes()
    repeated_validation = run_python(SPEC_OPS, "validate-delta", delta, specs)
    assert repeated_validation.returncode == 0, repeated_validation.stderr
    repeated_work = ready_state(SPEC_OPS, tmp_path / "repeated-state")
    repeated = apply_ready(SPEC_OPS, specs, delta, specs, repeated_work)
    assert repeated.returncode == 0, repeated.stderr
    assert (specs / "accounts" / "spec.md").read_bytes() == before
