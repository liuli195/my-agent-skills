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
        or (
            expected_item == "__snapshot_refspec_any__"
            and actual_item.startswith("+refs/heads/")
            and ":refs/pr-flow/" in actual_item
            and actual_item.endswith("/base")
        )
        for expected_item, actual_item in zip(expected, actual)
    )


def default_git_responses() -> list[tuple[tuple[str, ...], subprocess.CompletedProcess[str]]]:
    return [
        (("rev-parse", "--git-common-dir"), completed(["rev-parse", "--git-common-dir"], stdout=".git\n")),
        (("branch", "--show-current"), completed(["branch", "--show-current"], stdout="feature/example\n")),
        (
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"),
            completed(
                ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                stdout="origin/feature/example\n",
            ),
        ),
        (("rev-list", "--count", "@{u}..HEAD"), completed(["rev-list", "--count", "@{u}..HEAD"], stdout="0\n")),
        (("rev-list", "--count", "HEAD..@{u}"), completed(["rev-list", "--count", "HEAD..@{u}"], stdout="0\n")),
        (("status", "--porcelain"), completed(["status", "--porcelain"])),
        (("status", "--short"), completed(["status", "--short"])),
        (
            ("fetch", "--no-write-fetch-head", "--refmap=", "origin", "__snapshot_refspec_any__"),
            completed(["fetch", "--no-write-fetch-head", "--refmap=", "origin", "__snapshot_refspec_any__"]),
        ),
        (("rev-parse", "HEAD"), completed(["rev-parse", "HEAD"], stdout="b" * 40 + "\n")),
        (("rev-parse", "__snapshot_ref__"), completed(["rev-parse", "__snapshot_ref__"], stdout="a" * 40 + "\n")),
        (
            ("merge-base", "--is-ancestor", "__placeholder__", "__placeholder__"),
            completed(["merge-base", "--is-ancestor", "__placeholder__", "__placeholder__"]),
        ),
    ]


@dataclass
class CommandStub:
    responses: list[tuple[tuple[str, ...], subprocess.CompletedProcess[str]]] = field(default_factory=list)
    defaults: list[tuple[tuple[str, ...], subprocess.CompletedProcess[str]]] = field(default_factory=list)
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
        match_index = next(
            (
                index
                for index, (expected, _) in enumerate(self.responses)
                if expected == normalized or expected == call
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
        default_response = next(
            (
                response
                for expected, response in self.defaults
                if expected == normalized
                or expected == call
                or matches(expected, normalized)
                or matches(expected, call)
            ),
            None,
        )
        if default_response is not None:
            return completed(
                call,
                stdout=default_response.stdout,
                stderr=default_response.stderr,
                returncode=default_response.returncode,
            )
        return completed(call, stderr=f"unexpected_command: {' '.join(call)}\n", returncode=1)
