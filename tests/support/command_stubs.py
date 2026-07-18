from __future__ import annotations

import subprocess
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


def completed(
    args: Sequence[str],
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=list(args),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def matches(expected: tuple[str, ...], actual: tuple[str, ...]) -> bool:
    return len(expected) == len(actual) and all(
        expected_item == actual_item
        or expected_item == "__placeholder__"
        or (expected_item == "__snapshot_ref__" and actual_item.startswith("refs/pr-flow/") and actual_item.endswith("/base"))
        or (
            expected_item == "__snapshot_refspec__"
            and actual_item.startswith("+refs/heads/")
            and ":refs/pr-flow/" in actual_item
            and actual_item.endswith("/base")
        )
        for expected_item, actual_item in zip(expected, actual)
    )


def legacy_snapshot_alias(call: tuple[str, ...]) -> tuple[str, ...] | None:
    if len(call) == 5 and call[:4] == ("fetch", "--no-write-fetch-head", "--refmap=", "origin"):
        refspec = call[4]
        if refspec.startswith("+refs/heads/") and ":refs/pr-flow/" in refspec:
            branch = refspec.removeprefix("+refs/heads/").split(":", 1)[0]
            return ("fetch", "origin", branch)
    if len(call) == 2 and call[0] == "rev-parse" and call[1].startswith("refs/pr-flow/"):
        return ("rev-parse", "origin/main")
    return None


@dataclass
class CommandStub:
    responses: list[tuple[tuple[str, ...], subprocess.CompletedProcess[str]]] = field(default_factory=list)
    calls: list[tuple[str, ...]] = field(default_factory=list)
    body_files: list[dict[str, object]] = field(default_factory=list)
    consume: bool = False

    def add(
        self,
        args: Sequence[str],
        *,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        key = tuple(args)
        self.responses.append((key, completed(key, stdout=stdout, stderr=stderr, returncode=returncode)))

    def __call__(self, *args: Any, **_: Any) -> subprocess.CompletedProcess[str]:
        raw = tuple(str(arg) for arg in args)
        call = raw[1:] if args and isinstance(args[0], os.PathLike) else raw
        self.calls.append(call)
        if "--body-file" in call:
            body_index = call.index("--body-file") + 1
            body_path = call[body_index]
            with open(body_path, encoding="utf-8") as body:
                self.body_files.append({"args": call, "body": body.read()})
        normalized = call[1:] if call and call[0] == "gh" else call
        aliases = tuple(alias for candidate in (normalized, call) if (alias := legacy_snapshot_alias(candidate)) is not None)
        match_index = next(
            (
                index
                for index, (expected, _) in enumerate(self.responses)
                if expected == normalized or expected == call
            ),
            None,
        )
        if match_index is None and aliases:
            match_index = next(
                (
                    index
                    for index, (expected, _) in enumerate(self.responses)
                    if expected in aliases
                ),
                None,
            )
        if match_index is None:
            match_index = next(
                (
                    index
                    for index, (expected, _) in enumerate(self.responses)
                    if matches(expected, normalized) or matches(expected, call)
                ),
                None,
            )
        if match_index is not None:
            _, response = self.responses[match_index]
            if self.consume:
                self.responses.pop(match_index)
            return completed(
                call,
                stdout=response.stdout,
                stderr=response.stderr,
                returncode=response.returncode,
            )
        return completed(call, stderr=f"unexpected_command: {' '.join(call)}\n", returncode=1)
