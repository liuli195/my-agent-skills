"""awehitch 本地补丁的行为验收。

接缝（门禁一确认）：
  · 补丁 5 —— 命令行进、JSON 出：``awehitch status -w <仓库> --json``
  · 补丁 6/7 —— 渲染后的技能文本

这些检查针对的是**本机安装的 awehitch 包**，需要该包存在才可运行。
包、node 或 APPDATA 缺失时**明确跳过并说明原因**，绝不静默通过。
"""

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SERVICE_NAME = "awehitch-bridge"
# 本机实测：process.kill(<该值>, 0) 抛 ESRCH —— 确定不存在的进程号
DEAD_PID = 4_194_304
FOREIGN_WORKSPACE_ID = "deadbeef0000"

# 唯一发送通道的硬限制（awehitch_send_state 的前缀校验与字节上限）
C2C_PREFIX = "[C2C]"
C2C_LIMIT = 1024
# 引导词块与工作区校验块在渲染文本里的识别标记。
# 门禁一 Q10 决定不给模板加可机读标记，所以只能按内容识别。
BOOT_BLOCK_MARKER = "planning and review layer"
# 技能里**要发出去**的围栏文本块 —— 全部五块：引导词、两处工作区校验、INIT、EXECUTED。
SENT_BLOCK_MARKERS = (
    "planning and review layer",
    "workspace_info",
    "STATE: INIT",
    "STATE: EXECUTED",
)
# 票 02 明写**禁止**的说法：把重连失败的成因笼统说成「重启之后标志永不亮」。
# 准确的说法有两层：「状态不明」那一支才永不点亮；「已停止」那一支会亮，
# 只是只在一次运行的窗口内有效。
# 注意断言要精确到这个**笼统说法**——「…unknown 时永不为亮」是准确表述，不该被误伤。
FORBIDDEN_UNACCURATE_CLAIM = "after a reboot they never light up"
# 连接器名的最坏长度：名字直接吃字节预算，且不由本仓库控制
# （渲染名上限 40 字符，而旧名字只做 trim 不截断）。
WORST_CASE_CONNECTOR = "awehitch · " + "x" * 40


def _awehitch_package() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        pytest.skip("APPDATA 不可用 —— 这些检查只在本机装有 awehitch 包时可运行")
    package = Path(appdata) / "npm" / "node_modules" / "awehitch"
    if not package.is_dir():
        pytest.skip(f"未找到 awehitch 安装包（{package}）—— 这些检查只在本机装有该包时可运行")
    return package


def _awehitch_cli() -> Path:
    cli = _awehitch_package() / "dist" / "cli" / "index.js"
    if not cli.is_file():
        pytest.skip(f"未找到 awehitch 命令行入口（{cli}）—— 安装包结构可能已变")
    return cli


def _render_skill(connector_name: str, workdir: Path, harness: str = "Codex") -> str:
    """渲染技能文本 —— 就是产生该缺陷的那一步，两个客户端共用同一个渲染函数。"""
    node = _node()
    module = _awehitch_package() / "dist" / "adapters" / "skill-template.js"
    runner = workdir / "render-skill.mjs"
    runner.write_text(
        "import { pathToFileURL } from \"node:url\";\n"
        f"const mod = await import(pathToFileURL({json.dumps(module.as_posix())}).href);\n"
        f"process.stdout.write(mod.renderSkill({json.dumps({'harness': harness, 'connectorName': connector_name})}));\n",
        encoding="utf-8",
    )
    proc = subprocess.run([node, str(runner)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _node() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("未找到 node —— 这些检查需要 node 才可运行")
    return node


def _workspace_id(root: Path) -> str:
    """复刻 Workspace 的 id 算法：sha256(小写化的 realpath) 取前 12 位十六进制。"""
    return hashlib.sha256(os.path.realpath(root).lower().encode("utf-8")).hexdigest()[:12]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _ForeignHealth(BaseHTTPRequestHandler):
    """冒充「另一个工作区的 bridge」：/health 返回 200，但工作区标识对不上。"""

    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps(
            {
                "service": SERVICE_NAME,
                "workspaceId": FOREIGN_WORKSPACE_ID,
                "port": self.server.server_address[1],
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        return None


def test_status_treats_stale_record_as_not_running(tmp_path: Path) -> None:
    """记录里的进程已死时，不应因为端口被别的实例占着就判「状态不明」。"""
    cli, node = _awehitch_cli(), _node()

    root = tmp_path / "workspace"
    root.mkdir()
    state = tmp_path / "state"
    (state / "runtime").mkdir(parents=True)
    record = state / "runtime" / f"{_workspace_id(root)}.json"

    def write_record(pid: int, port: int) -> None:
        record.write_text(
            json.dumps(
                {
                    "service": SERVICE_NAME,
                    "version": "0.0.0-test",
                    "workspaceId": _workspace_id(root),
                    "workspaceRoot": str(root),
                    "pid": pid,
                    "port": port,
                    "adminToken": "test-admin-token",
                    "publicUrl": "",
                    "startedAt": "2020-01-01T00:00:00.000Z",
                }
            ),
            encoding="utf-8",
        )

    def status() -> dict:
        env = {**os.environ, "AWEHITCH_STATE_DIR": str(state)}
        proc = subprocess.run(
            [node, str(cli), "status", "-w", str(root), "--json"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        return json.loads(proc.stdout)

    # 前提：先证明「记录确实被读到了」——「状态不明」只可能来自一条被读到的记录。
    # 少了这一步，记录文件名一旦算错，本测试会因为「压根没有记录」而假绿。
    write_record(os.getpid(), _free_port())
    assert status()["state"] == "unknown"

    # 正题：记录里的进程已死，而它记录的那个端口被「别的实例」占着。
    server = HTTPServer(("127.0.0.1", 0), _ForeignHealth)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        write_record(DEAD_PID, int(server.server_address[1]))
        payload = status()
        assert payload["running"] is False
        assert payload.get("state") != "unknown"

        # 边界：进程仍在（"进程号被回收"后同样表现为「存在」）而端口上不是本工作区的
        # 服务时，仍须**保持保守** —— 判「状态不明」，不得误判成可以启动。
        # 这条是本次**明确不修**的一支，用来确认它没被顺手改坏。
        write_record(os.getpid(), int(server.server_address[1]))
        assert status()["state"] == "unknown"
    finally:
        server.shutdown()
        server.server_close()


def test_rendered_skill_reconnect_flow_rebuilds_the_connector(tmp_path: Path) -> None:
    """连不上时，技能必须指引 Agent（代理）跑唯一真正重建连接的那一步。"""
    text = _render_skill("awehitch · my-agent-skills", tmp_path)

    # 唯一真正重建连接的一步，必须在技能里给出。
    assert "connector-setup" in text

    # 不再把重连的触发条件挂在两个标志位上（模板里原有两处引用，都要清掉）。
    assert "chatgptRepair" not in text
    assert "chatgptSetup" not in text

    # 「本地不全绿就不开 ChatGPT」这道门禁已删除 —— 它既不亮也不准，实测误导。
    assert "do not open ChatGPT" not in text


def _fenced_blocks(text: str) -> list[str]:
    return re.findall(r"```[^\n]*\n(.*?)```", text, re.S)


def test_rendered_skill_messages_fit_the_c2c_channel(tmp_path: Path) -> None:
    """技能里声明为「要发出去」的文本块，必须真的能通过唯一的发送通道。"""
    blocks = _fenced_blocks(_render_skill(WORST_CASE_CONNECTOR, tmp_path))

    sent = [block for block in blocks if any(m in block for m in SENT_BLOCK_MARKERS)]
    assert len(sent) == 5, f"应当有 5 个送出的文本块，实到 {len(sent)} 个"

    for block in sent:
        assert block.lstrip().startswith(C2C_PREFIX), (
            f"送出的文本块必须以 [C2C] 开头，否则发送通道会拒收：{block.splitlines()[0][:40]!r}"
        )
        size = len(block.encode("utf-8"))
        assert size <= C2C_LIMIT, f"送出的文本块 {size} 字节，超过发送通道的 {C2C_LIMIT} 字节上限"

    boot = [block for block in blocks if BOOT_BLOCK_MARKER in block]
    assert len(boot) == 1, "应当恰好有一个引导词块"
    assert WORST_CASE_CONNECTOR in boot[0], "引导词里要保留连接器名，否则可能读错工作区"


def test_rendered_skill_states_the_reconnect_reason_accurately(tmp_path: Path) -> None:
    """票 02 明写：不得把成因笼统说成「重启后标志永不亮」——那是被证伪的说法。

    散文的准确性本身只能靠人审；这里只钉住**那句被点名禁止的说法**不许回归。
    """
    text = _render_skill("awehitch · my-agent-skills", tmp_path)
    assert FORBIDDEN_UNACCURATE_CLAIM not in text
