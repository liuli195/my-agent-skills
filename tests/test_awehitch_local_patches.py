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


def _awehitch_cli() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        pytest.skip("APPDATA 不可用 —— 这些检查只在本机装有 awehitch 包时可运行")
    cli = Path(appdata) / "npm" / "node_modules" / "awehitch" / "dist" / "cli" / "index.js"
    if not cli.is_file():
        pytest.skip(f"未找到 awehitch 安装包（{cli}）—— 这些检查只在本机装有该包时可运行")
    return cli


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
