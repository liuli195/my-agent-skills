"""awehitch 0.3.2 本地补丁的行为验收。"""

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

C2C_LIMIT = 1024
WORST_CASE_CONNECTOR = "awehitch · " + "x" * 40


def _package() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        pytest.skip("APPDATA 不可用")
    package = Path(appdata) / "npm" / "node_modules" / "awehitch"
    if not package.is_dir():
        pytest.skip(f"未找到 awehitch 安装包：{package}")
    return package


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("未找到 node")
    return node


def _powershell() -> str:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        pytest.skip("未找到 PowerShell")
    return powershell


def _isolated_package(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Copy the release into isolated Windows profile roots before patching it."""
    source = _package()
    appdata = tmp_path / "appdata"
    package = appdata / "npm" / "node_modules" / "awehitch"
    shutil.copytree(source, package)
    for relative in (
        "dist/adapters/codex.js",
        "dist/cli/index.js",
        "dist/control-plane/browser.js",
        "dist/control-plane/composer.js",
        "dist/control-plane/connector.js",
        "skill/SKILL.md.template",
    ):
        original = package / (relative + ".orig")
        if original.is_file():
            shutil.copyfile(original, package / relative)
    environment = os.environ.copy()
    environment.update(
        {
            "APPDATA": str(appdata),
            "LOCALAPPDATA": str(tmp_path / "localappdata"),
            "USERPROFILE": str(tmp_path / "userprofile"),
            "CODEX_HOME": str(tmp_path / "codex"),
            "AWEHITCH_STATE_DIR": str(tmp_path / "state"),
        }
    )
    return package, environment


def _run_local_patch(tmp_path: Path) -> tuple[Path, dict[str, str], subprocess.CompletedProcess[str]]:
    package, environment = _isolated_package(tmp_path)
    script = Path(__file__).parents[1] / "scripts" / "awehitch-local-patches.ps1"
    result = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return package, environment, result


def _invoke_patch(environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).parents[1] / "scripts" / "awehitch-local-patches.ps1"
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _install_legacy_project_local_patch(package: Path) -> None:
    codex = package / "dist" / "adapters" / "codex.js"
    cli = package / "dist" / "cli" / "index.js"
    codex_text = codex.read_text(encoding="utf-8")
    old_return = (
        "    return { skillInstalled: fs.existsSync(skillPath), mcpRegistered, "
        "sandboxAllowed, configPath };"
    )
    old_check = (
        '    if (!mcpRegistered && workspace?.root) {\n'
        "        try {\n"
        '            const projectConfig = fs.readFileSync(path.join(workspace.root, ".codex", "config.toml"), "utf8");\n'
        "            mcpRegistered = /\\[mcp_servers\\.awehitch\\]/.test(projectConfig);\n"
        "        }\n"
        "        catch {\n"
        "            // This workspace has no project-level Codex registration.\n"
        "        }\n"
        "    }\n"
    )
    codex_text = codex_text.replace(
        "    const next = upsertCodexMcpEntry(previous, opts.cliEntry, opts.workspaceRoot);",
        "    const next = previous; // PATCH(local): keep Codex registration project-local",
    ).replace(
        "export function codexAdapterStatus() {",
        "export function codexAdapterStatus(workspace) { // PATCH(local): keep Codex registration project-local",
    ).replace(old_return, old_check + old_return)
    codex.write_bytes(codex_text.encode("utf-8"))
    cli_text = cli.read_text(encoding="utf-8").replace(
            "            const status = impl.status();",
            "            const status = impl.status(workspace); // PATCH(local): keep Codex registration project-local",
    )
    cli.write_bytes(cli_text.encode("utf-8"))


def _status(package: Path, workspace: Path, environment: dict[str, str], tmp_path: Path) -> dict:
    runner = tmp_path / "status.mjs"
    module = package / "dist" / "adapters" / "codex.js"
    runner.write_text(
        'import { pathToFileURL } from "node:url";\n'
        f"const m = await import(pathToFileURL({json.dumps(module.as_posix())}).href);\n"
        f"process.stdout.write(JSON.stringify(m.codexAdapterStatus({{root: {json.dumps(str(workspace))}}})));\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [_node(), str(runner)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _render_skill(connector: str, tmp_path: Path) -> str:
    module = _package() / "dist" / "adapters" / "skill-template.js"
    runner = tmp_path / "render.mjs"
    runner.write_text(
        'import { pathToFileURL } from "node:url";\n'
        f"const m = await import(pathToFileURL({json.dumps(module.as_posix())}).href);\n"
        f"process.stdout.write(m.renderSkill({json.dumps({'harness': 'Codex', 'connectorName': connector})}));\n",
        encoding="utf-8",
    )
    result = subprocess.run([_node(), str(runner)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _render_package_skill(package: Path, connector: str, tmp_path: Path) -> str:
    module = package / "dist" / "adapters" / "skill-template.js"
    runner = tmp_path / "render-isolated.mjs"
    runner.write_text(
        'import { pathToFileURL } from "node:url";\n'
        f"const m = await import(pathToFileURL({json.dumps(module.as_posix())}).href);\n"
        f"process.stdout.write(m.renderSkill({json.dumps({'harness': 'Codex', 'harnessId': 'codex', 'connectorName': connector})}));\n",
        encoding="utf-8",
    )
    result = subprocess.run([_node(), str(runner)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_patch_set_is_pinned_to_the_tested_release() -> None:
    package = _package()
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    assert metadata["version"] == "0.3.2"

    script = (Path(__file__).parents[1] / "scripts" / "awehitch-local-patches.ps1").read_text(encoding="utf-8")
    assert "补丁 1" in script and "补丁 3" in script and "补丁 4" in script and "补丁 7" in script
    assert "补丁 2：" not in script and "补丁 5：" not in script and "补丁 6：" not in script


def test_project_config_pins_codex_harness_and_three_slots() -> None:
    config = tomllib.loads(
        (Path(__file__).parents[1] / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    entry = config["mcp_servers"]["awehitch"]
    args = entry["args"]
    assert args[args.index("--harness") + 1] == "codex"
    assert entry["env"]["AWEHITCH_MAX_PARALLEL_SESSIONS"] == "3"


def test_local_patch_runs_in_isolated_profile_and_status_accepts_fixed_project_config(
    tmp_path: Path,
) -> None:
    package, environment, result = _run_local_patch(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr

    workspace = tmp_path / "workspace"
    (workspace / ".codex").mkdir(parents=True)
    project_config = (
        "[mcp_servers.awehitch]\n"
        'command = "node"\n'
        f'args = ["control-plane", "--workspace", {json.dumps(str(workspace))}, "--harness", "codex"]\n'
        'env = { AWEHITCH_CONTROL_PLANE = "1", AWEHITCH_MAX_PARALLEL_SESSIONS = "3" }\n'
    )
    (workspace / ".codex" / "config.toml").write_text(project_config, encoding="utf-8")
    status = _status(package, workspace, environment, tmp_path)
    assert status["mcpRegistered"] is True


@pytest.mark.parametrize(
    "change",
    [
        "wrong workspace",
        "wrong harness",
        "wrong slot count",
        "missing control plane",
        "legacy transport",
        "comment bait",
        "inline comment bait",
    ],
)
def test_status_rejects_non_fixed_project_registration(
    tmp_path: Path, change: str
) -> None:
    package, environment, result = _run_local_patch(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr

    workspace = tmp_path / "workspace"
    (workspace / ".codex").mkdir(parents=True)
    configured_workspace = workspace
    harness = '"--harness", "codex"'
    slots = 'AWEHITCH_MAX_PARALLEL_SESSIONS = "3"'
    control_plane = 'AWEHITCH_CONTROL_PLANE = "1"'
    transport = ""
    comments = ""
    args_suffix = ""
    env_suffix = ""
    if change == "wrong workspace":
        configured_workspace = tmp_path / "other-workspace"
    elif change == "wrong harness":
        harness = '"--harness", "opencode"'
    elif change == "wrong slot count":
        slots = 'AWEHITCH_MAX_PARALLEL_SESSIONS = "2"'
    elif change == "missing control plane":
        control_plane = 'OTHER_SETTING = "1"'
    elif change == "legacy transport":
        transport = 'type = "stdio"\n'
    elif change == "comment bait":
        harness = '"--harness", "opencode"'
        slots = 'AWEHITCH_MAX_PARALLEL_SESSIONS = "2"'
        control_plane = 'AWEHITCH_CONTROL_PLANE = "0"'
        comments = (
            f'# args = ["control-plane", "--workspace", {json.dumps(str(workspace))}, "--harness", "codex"]\n'
            '# env = { AWEHITCH_CONTROL_PLANE = "1", AWEHITCH_MAX_PARALLEL_SESSIONS = "3" }\n'
        )
    elif change == "inline comment bait":
        harness = '"--harness", "opencode"'
        slots = 'AWEHITCH_MAX_PARALLEL_SESSIONS = "2"'
        control_plane = 'AWEHITCH_CONTROL_PLANE = "0"'
        args_suffix = (
            f' # expected args = ["control-plane", "--workspace", {json.dumps(str(workspace))}, "--harness", "codex"]'
        )
        env_suffix = (
            ' # expected env = { AWEHITCH_CONTROL_PLANE = "1", '
            'AWEHITCH_MAX_PARALLEL_SESSIONS = "3" }'
        )
    project_config = (
        "[mcp_servers.awehitch]\n"
        f"{comments}"
        f"{transport}"
        'command = "node"\n'
        f'args = ["control-plane", "--workspace", {json.dumps(str(configured_workspace))}, {harness}]{args_suffix}\n'
        f'env = {{ {control_plane}, {slots} }}{env_suffix}\n'
    )
    (workspace / ".codex" / "config.toml").write_text(project_config, encoding="utf-8")
    status = _status(package, workspace, environment, tmp_path)
    assert status["mcpRegistered"] is False, change


def test_local_patch_is_idempotent_in_the_isolated_profile(tmp_path: Path) -> None:
    package, environment = _isolated_package(tmp_path)
    codex_home_config = Path(environment["CODEX_HOME"]) / "config.toml"
    profile_config = Path(environment["USERPROFILE"]) / ".codex" / "config.toml"
    sentinel = b'\xef\xbb\xbf# preserve these exact bytes\r\nmodel = "example"\r\n'
    for config in (codex_home_config, profile_config):
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_bytes(sentinel)

    first = _invoke_patch(environment)
    assert first.returncode == 0, first.stdout + first.stderr
    tracked = [
        package / "dist" / "adapters" / "codex.js",
        package / "dist" / "cli" / "index.js",
        package / "dist" / "control-plane" / "browser.js",
        package / "dist" / "control-plane" / "composer.js",
        package / "dist" / "control-plane" / "connector.js",
        package / "skill" / "SKILL.md.template",
    ]
    before = {path: path.read_bytes() for path in tracked}
    second = _invoke_patch(environment)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "两个文件均有完整最终特征" in second.stdout
    assert before == {path: path.read_bytes() for path in tracked}
    assert codex_home_config.read_bytes() == sentinel
    assert profile_config.read_bytes() == sentinel


def test_local_patch_upgrades_the_exact_legacy_project_local_patch(tmp_path: Path) -> None:
    package, environment = _isolated_package(tmp_path)
    _install_legacy_project_local_patch(package)

    result = _invoke_patch(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    codex = (package / "dist" / "adapters" / "codex.js").read_text(encoding="utf-8")
    assert "validate comment-safe fixed project config" in codex
    assert "function hasValidProjectRegistration(content, workspaceRoot)" in codex


def test_local_patch_upgrades_the_exact_complete_validator_without_comment_safety(tmp_path: Path) -> None:
    package, environment, first = _run_local_patch(tmp_path)
    assert first.returncode == 0, first.stdout + first.stderr
    codex_path = package / "dist" / "adapters" / "codex.js"
    cli_path = package / "dist" / "cli" / "index.js"
    final_marker = "validate comment-safe fixed project config"
    previous_marker = "validate complete fixed project config"
    codex = codex_path.read_text(encoding="utf-8").replace(final_marker, previous_marker)
    codex = codex.replace("([^\\r\\n]*?)", "([^\\r\\n]*)")
    codex = codex.replace(
        "validate comment-safe fixed project registration",
        "validate complete fixed project registration",
    )
    codex_path.write_bytes(codex.encode("utf-8"))
    cli_path.write_bytes(
        cli_path.read_text(encoding="utf-8").replace(final_marker, previous_marker).encode("utf-8")
    )

    result = _invoke_patch(environment)

    assert result.returncode == 0, result.stdout + result.stderr
    upgraded = codex_path.read_text(encoding="utf-8")
    assert final_marker in upgraded
    assert "([^\\r\\n]*?)" in upgraded


def test_local_patch_does_not_touch_ambiguous_codex_adapter(tmp_path: Path) -> None:
    package, environment = _isolated_package(tmp_path)
    codex = package / "dist" / "adapters" / "codex.js"
    before = codex.read_bytes()
    codex.write_text(
        codex.read_text(encoding="utf-8")
        + '\n    const next = upsertCodexMcpEntry(previous, opts.cliEntry, opts.workspaceRoot);\n',
        encoding="utf-8",
    )
    ambiguous = codex.read_bytes()
    result = _invoke_patch(environment)
    assert result.returncode != 0
    assert "判不准" in result.stdout
    assert codex.read_bytes() == ambiguous
    assert codex.read_bytes() != before
    assert "const next = previous; // PATCH(local):" not in codex.read_text(encoding="utf-8")


def test_selector_override_is_merged_without_losing_unknown_fields(tmp_path: Path) -> None:
    package, environment = _isolated_package(tmp_path)
    selector_file = Path(environment["AWEHITCH_STATE_DIR"]) / "control-plane" / "selectors.json"
    selector_file.parent.mkdir(parents=True)
    selector_file.write_text(
        json.dumps(
            {
                "version": "custom-version",
                "selectors": {"composer": "#custom-composer"},
                "connector": {"connectButton": ["button.custom-connect"]},
            }
        ),
        encoding="utf-8",
    )

    first = _invoke_patch(environment)
    assert first.returncode == 0, first.stdout + first.stderr
    data = json.loads(selector_file.read_text(encoding="utf-8"))
    assert data["version"] == "custom-version"
    assert data["selectors"]["composer"] == "#custom-composer"
    assert data["connector"]["connectButton"] == ["button.custom-connect"]
    assert data["connector"]["signInButton"] == [
        "[role='dialog']:has-text('添加到 ChatGPT') button:has-text('登录')",
        "button:has-text('使用 awehitch')",
        "[role='dialog']:has-text('Add ') button:has-text('Sign in')",
        "[role='alertdialog'] button:has-text('Sign in')",
    ]
    before = selector_file.read_bytes()
    second = _invoke_patch(environment)
    assert second.returncode == 0, second.stdout + second.stderr
    assert selector_file.read_bytes() == before


@pytest.mark.parametrize(
    "contents",
    ['{"connector":{"signInButton":["custom"]}}', '{"connector":{"signInButton":[]}}', "{broken", "[]"],
)
def test_selector_override_drift_or_invalid_json_is_not_overwritten(
    tmp_path: Path, contents: str
) -> None:
    _, environment = _isolated_package(tmp_path)
    selector_file = Path(environment["AWEHITCH_STATE_DIR"]) / "control-plane" / "selectors.json"
    selector_file.parent.mkdir(parents=True)
    selector_file.write_text(contents, encoding="utf-8")
    before = selector_file.read_bytes()

    result = _invoke_patch(environment)

    assert result.returncode != 0
    assert "授权按钮选择器" in result.stdout
    assert selector_file.read_bytes() == before


def test_authorization_observer_covers_each_safe_stage(tmp_path: Path) -> None:
    package, environment, result = _run_local_patch(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    connector = (package / "dist" / "control-plane" / "connector.js").read_text(
        encoding="utf-8"
    )
    for marker in (
        "[AUTH-OBS] selectors-loaded",
        "[AUTH-OBS] connect-click",
        "[AUTH-OBS] sign-in-state",
        "[AUTH-OBS] sign-in-click",
        "[AUTH-OBS] authorize-page",
        "[AUTH-OBS] authorization-verify",
    ):
        assert marker in connector
    observer_lines = "\n".join(
        line for line in connector.splitlines() if "AUTH-OBS" in line
    )
    assert "const signInDeadline = signInStartedAt + 10_000;" in connector
    assert "selector:" not in observer_lines
    assert "error.message" not in observer_lines
    assert "pairingCode" not in observer_lines
    assert "accessToken" not in observer_lines
    assert "refreshToken" not in observer_lines
    checked = subprocess.run(
        [_node(), "--check", str(package / "dist" / "control-plane" / "connector.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr


def test_fold_toggle_is_removed_by_the_real_compare_function(tmp_path: Path) -> None:
    module = _package() / "dist" / "control-plane" / "composer.js"
    runner = tmp_path / "normalize.mjs"
    runner.write_text(
        'import { pathToFileURL } from "node:url";\n'
        f"const m = await import(pathToFileURL({json.dumps(module.as_posix())}).href);\n"
        'process.stdout.write(JSON.stringify([m.normalizeForCompare("payload Show more"), m.normalizeForCompare("payload 展开")]));\n',
        encoding="utf-8",
    )
    result = subprocess.run([_node(), str(runner)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["payload", "payload"]


def test_codex_adapter_keeps_registration_project_local(tmp_path: Path) -> None:
    package, _, result = _run_local_patch(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    codex = (package / "dist" / "adapters" / "codex.js").read_text(encoding="utf-8")
    cli = (package / "dist" / "cli" / "index.js").read_text(encoding="utf-8")
    assert "const next = previous; // PATCH(local): keep Codex registration project-local and validate comment-safe fixed project config" in codex
    assert 'path.join(workspace.root, ".codex", "config.toml")' in codex
    assert "function hasValidProjectRegistration(content, workspaceRoot)" in codex
    assert "mcpRegistered = hasValidProjectRegistration(projectConfig, workspace.root);" in codex
    assert "impl.status(workspace)" in cli

    script = (Path(__file__).parents[1] / "scripts" / "awehitch-local-patches.ps1").read_text(encoding="utf-8")
    assert "$cxDone=" in script and "$clDone=" in script
    assert "if ($cxDone -and $clDone)" in script


def test_rendered_skill_uses_status_first_for_steady_state_workflows(tmp_path: Path) -> None:
    package, _, result = _run_local_patch(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    text = _render_package_skill(package, WORST_CASE_CONNECTOR, tmp_path)

    quick = text.split('## Workflow: quick question', 1)[1].split(
        '## Workflow: coding task', 1
    )[0]
    coding = text.split('## Workflow: coding task', 1)[1].split(
        '## Workflow: dispatched', 1
    )[0]
    assert "awehitch status --json" in quick
    assert "awehitch doctor -w <workspace> --no-fix --json" in quick
    assert "do not run `up`" in quick
    assert "awehitch status --json" in coding
    assert re.search(
        r"awehitch doctor -w\s+<workspace> --no-fix --json", coding
    )
    assert "(auto-repairs)" not in coding


def test_rendered_messages_fit_the_real_c2c_channel(tmp_path: Path) -> None:
    text = _render_skill(WORST_CASE_CONNECTOR, tmp_path)
    blocks = re.findall(r"```[^\n]*\n(.*?)```", text, re.S)
    expected_states = {"BOOT", "QUICK_QUESTION", "CONNECT_CHECK", "INIT", "EXECUTED", "FOLLOW"}
    sent = [
        block
        for block in blocks
        if re.search(r"(?m)^STATE: (?:BOOT|QUICK_QUESTION|CONNECT_CHECK|INIT|EXECUTED|FOLLOW)$", block)
    ]
    actual_states = {
        match.group(1)
        for block in sent
        if (match := re.search(r"(?m)^STATE: (\w+)$", block))
    }
    assert actual_states == expected_states
    for block in sent:
        assert block.lstrip().startswith("[C2C]")
        assert len(block.encode("utf-8")) <= C2C_LIMIT

    boot = [block for block in sent if "STATE: BOOT" in block]
    assert len(boot) == 1
    assert WORST_CASE_CONNECTOR in boot[0]
