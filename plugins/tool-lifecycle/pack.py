from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

MANAGEMENT = Path(__file__).with_name("python") / "management.py"

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = {
    "myspec": (ROOT / "plugins" / "my-spec", "@liuli195/myspec"),
    "build-and-verify": (ROOT / "plugins" / "build-and-verify", "@liuli195/build-and-verify"),
}


def _validate_package(package: Path, expected_name: str) -> None:
    try:
        manifest = json.loads((package / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid_package_manifest: {package}") from error
    if not isinstance(manifest, dict) or manifest.get("name") != expected_name:
        raise ValueError(f"invalid_package_name: {package}")


def _validate_tarball(path: Path, expected_name: str) -> None:
    try:
        with tarfile.open(path, "r:gz") as archive:
            manifest = archive.extractfile("package/package.json")
            if manifest is None:
                raise ValueError(f"invalid_tarball_manifest: {path}")
            value = json.loads(manifest.read().decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid_tarball_manifest: {path}") from error
    if not isinstance(value, dict) or value.get("name") != expected_name:
        raise ValueError(f"invalid_tarball_name: {path}")


def pack(name: str, output: Path) -> Path:
    output = output.resolve()
    selected = PACKAGES.get(name)
    if selected is None:
        raise ValueError(f"unknown_package: {name}")
    source, package_name = selected
    if output.is_relative_to(ROOT):
        raise ValueError("output_inside_repository")
    _validate_package(source, package_name)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{name}-pack-") as temporary:
        package = Path(temporary) / name
        shutil.copytree(source, package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        _validate_package(package, package_name)
        shutil.copy2(MANAGEMENT, package / "python" / "management.py")
        _validate_package(package, package_name)
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError("missing_command: npm")
        command = [npm, "pack", "--ignore-scripts", "--json", "--pack-destination", str(output)]
        result = subprocess.run(
            subprocess.list2cmdline(command) if os.name == "nt" and npm.endswith((".cmd", ".bat")) else command,
            cwd=package,
            text=True,
            capture_output=True,
            check=False,
            shell=os.name == "nt" and npm.endswith((".cmd", ".bat")),
        )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "npm_pack_failed")
    payload = json.loads(result.stdout)
    if not isinstance(payload, list) or len(payload) != 1 or not isinstance(payload[0], dict):
        raise RuntimeError("invalid_npm_pack_output")
    filename = payload[0].get("filename")
    if not isinstance(filename, str):
        raise RuntimeError("invalid_npm_pack_output")
    tarball = output / filename
    _validate_tarball(tarball, package_name)
    return tarball


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", choices=PACKAGES)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        print(pack(args.package, args.output))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
