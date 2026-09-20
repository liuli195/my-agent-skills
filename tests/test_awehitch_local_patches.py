"""awehitch 0.3.2 本地补丁的行为验收。"""

import json
import os
import re
import shutil
import subprocess
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


def test_patch_set_is_pinned_to_the_tested_release() -> None:
    package = _package()
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    assert metadata["version"] == "0.3.2"

    script = (Path(__file__).parents[1] / "scripts" / "awehitch-local-patches.ps1").read_text(encoding="utf-8")
    assert "补丁 1" in script and "补丁 3" in script and "补丁 4" in script and "补丁 7" in script
    assert "补丁 2：" not in script and "补丁 5：" not in script and "补丁 6：" not in script


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


def test_codex_adapter_keeps_registration_project_local() -> None:
    codex = (_package() / "dist" / "adapters" / "codex.js").read_text(encoding="utf-8")
    cli = (_package() / "dist" / "cli" / "index.js").read_text(encoding="utf-8")
    assert "const next = previous; // PATCH(local): keep Codex registration project-local" in codex
    assert 'path.join(workspace.root, ".codex", "config.toml")' in codex
    assert "impl.status(workspace)" in cli

    script = (Path(__file__).parents[1] / "scripts" / "awehitch-local-patches.ps1").read_text(encoding="utf-8")
    assert "$cxDone=" in script and "$clDone=" in script
    assert "if ($cxDone -and $clDone)" in script


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
