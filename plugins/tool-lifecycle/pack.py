from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
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


def _inject_management(package: Path, expected_name: str, management: Path = MANAGEMENT) -> None:
    _validate_package(package, expected_name)
    shutil.copy2(management, package / "python" / "management.py")
    _validate_package(package, expected_name)


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
        _inject_management(package, package_name)
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


def _release_flow(project: Path):
    path = project / "plugins/release-flow/skills/release-flow/scripts/release_flow.py"
    spec = importlib.util.spec_from_file_location("snapshot_release_registry", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(project: Path, *arguments: str) -> str:
    result = subprocess.run(["git", "-C", str(project), *arguments],
                            text=True, capture_output=True, check=False, timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "snapshot_git_failed")
    return result.stdout


def _snapshot_inputs(project: Path, name: str, record: dict) -> tuple[Path, list[Path], str]:
    paths = record["releaseInputs"]
    for raw in paths:
        relative = Path(raw)
        path = project / relative
        if relative.is_absolute() or ".." in relative.parts or not path.resolve().is_relative_to(project):
            raise ValueError(f"snapshot_input_outside_project: {raw}")
        if not path.exists():
            raise ValueError(f"snapshot_input_missing: {raw}")
    files = []
    digest = hashlib.sha256(json.dumps(record, sort_keys=True).encode())
    digest.update(Path(__file__).read_bytes())
    for raw in sorted(set(_git(project, "ls-files", "-z", "--cached", "--others",
                               "--exclude-standard", "--", *paths).split("\0")) - {""}):
        relative = Path(raw)
        path = project / relative
        if not path.resolve().is_relative_to(project) or path.is_symlink():
            raise ValueError(f"snapshot_input_link: {raw}")
        if not path.is_file():
            if relative.name == "SKILL.md":
                raise ValueError(f"snapshot_skill_input_missing: {raw}")
            continue
        if any(part in {"__pycache__", "node_modules", ".git"} for part in relative.parts) or path.suffix == ".pyc":
            continue
        files.append(relative)
        digest.update(raw.encode() + b"\0" + str(path.stat().st_mode & 0o777).encode() + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    root = Path(paths[0])
    if not files or root == Path("."):
        raise ValueError(f"snapshot_inputs_empty: {name}")
    return root, files, digest.hexdigest()


def _snapshot_version(package: Path, name: str) -> str:
    manifests = [json.loads((package / client / "plugin.json").read_text(encoding="utf-8"))
                 for client in (".codex-plugin", ".claude-plugin")]
    version = manifests[0].get("version")
    _validate_cloud_metadata(manifests[0])
    for manifest in manifests:
        skills = Path(manifest["skills"])
        if (manifest.get("name") != name or not version or manifest.get("version") != version
                or skills.is_absolute() or ".." in skills.parts
                or not list((package / skills).rglob("SKILL.md"))):
            raise ValueError(f"snapshot_plugin_invalid: {name}")
    package_manifest = package / "package.json"
    if package_manifest.exists() and json.loads(package_manifest.read_text(encoding="utf-8")).get("version") != version:
        raise ValueError(f"snapshot_package_version_mismatch: {name}")
    return version


def _cloud_metadata(package: Path, name: str, record: dict) -> dict:
    path = package / ".codex-plugin/plugin.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    owner = record["snapshotRepository"].split("/", 1)[0]
    manifest.setdefault("author", {"name": owner})
    interface = manifest.setdefault("interface", {})
    if not isinstance(manifest["author"], dict) or not isinstance(interface, dict):
        raise ValueError("snapshot_cloud_metadata_invalid")
    sources = {field: ".codex-plugin/plugin.json" if field in interface else fallback
               for field, fallback in {"category": "release registry", "capabilities": "no declared labels"}.items()}
    for field, value in {
        "displayName": name,
        "shortDescription": " ".join(manifest["description"].splitlines()),
        "longDescription": manifest["description"],
        "developerName": manifest["author"]["name"],
        "category": record["codexMarketplace"]["category"],
        "capabilities": [],
    }.items():
        interface.setdefault(field, value)
    _validate_cloud_metadata(manifest)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sources


def _validate_cloud_metadata(manifest: dict) -> None:
    # Package limits, not the stricter public-directory submission limits.
    author = manifest["author"]["name"]
    if not isinstance(author, str) or not author.strip() or len(author) > 120:
        raise ValueError("snapshot_cloud_author_invalid")
    interface = manifest["interface"]
    for field, limit in {"displayName": 80, "shortDescription": 240,
                         "longDescription": 4000, "developerName": 120}.items():
        value = interface[field]
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"snapshot_cloud_interface_invalid: {field}")
    if len(interface["shortDescription"].splitlines()) != 1:
        raise ValueError("snapshot_cloud_short_description_multiline")
    if interface["category"] not in {
        "Developer Tools", "Productivity", "Creativity", "Business & Operations", "Data & Analytics",
        "Communication", "Education & Research", "Security", "Finance", "Healthcare", "Travel",
        "Entertainment", "Other",
    }:
        raise ValueError("snapshot_cloud_category_invalid")
    capabilities = interface["capabilities"]
    if not isinstance(capabilities, list) or len(capabilities) > 20 or any(
        not isinstance(value, str) or not value.strip() or len(value) > 120 or len(value.splitlines()) != 1
        for value in capabilities
    ):
        raise ValueError("snapshot_cloud_capabilities_invalid")


def _same_directory(directory: Path, artifact: Path) -> bool:
    if not directory.is_dir() or directory.is_symlink():
        return False
    files = {path.relative_to(directory).as_posix(): path for path in directory.rglob("*") if path.is_file()}
    with zipfile.ZipFile(artifact) as archive:
        return set(files) == set(archive.namelist()) and all(
            not path.is_symlink() and path.read_bytes() == archive.read(name)
            and (os.name == "nt" or archive.getinfo(name).create_system != 3
                 or (path.stat().st_mode & 0o111) == ((archive.getinfo(name).external_attr >> 16) & 0o111))
            for name, path in files.items()
        )


def snapshots(project: Path, output: Path) -> dict:
    """Build complete, local-only plugin archives; never publish or install."""
    project, output = project.resolve(), output.resolve()
    flow = _release_flow(project)
    repository = flow.github_repository_identity(project)
    registry = {name: record | {"snapshotRepository": repository} for name, record in flow.PLUGIN_REGISTRY.items()}
    inputs = {name: _snapshot_inputs(project, name, record) for name, record in registry.items()}
    if any(output.is_relative_to(project / root) for root, _files, _digest in inputs.values()):
        raise ValueError("snapshot_output_inside_release_input")
    commit = _git(project, "rev-parse", "HEAD").strip()
    dirty = bool(_git(project, "status", "--porcelain"))
    output.mkdir(parents=True, exist_ok=True)
    previous_path = output / "snapshots.json"
    previous = json.loads(previous_path.read_text(encoding="utf-8")) if previous_path.exists() else {}
    if previous and previous.get("version") != 1:
        raise ValueError("snapshot_manifest_version_invalid")
    manifest = {"version": 1, "plugins": {}}
    built, reused = [], []
    with tempfile.TemporaryDirectory(prefix=".snapshots-", dir=output) as temporary:
        temporary = Path(temporary)
        for name, record in registry.items():
            started = time.monotonic()
            root, files, digest = inputs[name]
            saved = previous.get("plugins", {}).get(name, {})
            if saved.get("inputVersion") == digest:
                artifact = output / saved["artifact"]
                if (artifact.parent != output or artifact.is_symlink() or not artifact.is_file()
                        or hashlib.sha256(artifact.read_bytes()).hexdigest() != saved["sha256"]
                        or artifact.stat().st_size != saved["sizeBytes"]
                        or Path(saved["pluginPath"]).parent != output
                        or not _same_directory(Path(saved["pluginPath"]), artifact)):
                    raise ValueError(f"snapshot_previous_artifact_invalid: {name}")
                manifest["plugins"][name] = saved
                reused.append(name)
                continue
            package = temporary / name
            for relative in files:
                if relative.is_relative_to(root):
                    destination = package / relative.relative_to(root)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(project / relative, destination)
            if record.get("commandTool"):
                _inject_management(package, record["commandTool"]["package"],
                                   project / MANAGEMENT.relative_to(ROOT))
            metadata_sources = _cloud_metadata(package, name, record)
            version = _snapshot_version(package, name)
            filename = f"{name}-{digest[:20]}.zip"
            artifact = temporary / filename
            with zipfile.ZipFile(artifact, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(package.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(package).as_posix())
            manifest["plugins"][name] = {
                "inputVersion": digest, "sourceCommit": commit, "sourceDirty": dirty, "version": version,
                "artifact": filename, "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "sizeBytes": artifact.stat().st_size, "buildSeconds": round(time.monotonic() - started, 6),
                "pluginPath": str(output / filename.removesuffix(".zip")),
                "metadataSource": {"repository": repository, "description": ".codex-plugin/plugin.json",
                                   **metadata_sources},
            }
            built.append(name)
        # A concurrent source edit must not publish a manifest for mixed inputs.
        if any(_snapshot_inputs(project, name, record)[2] != inputs[name][2]
               for name, record in registry.items()):
            raise ValueError("snapshot_inputs_changed_during_build")
        for name in built:
            filename = manifest["plugins"][name]["artifact"]
            directory = Path(manifest["plugins"][name]["pluginPath"])
            if directory.exists() and not _same_directory(directory, temporary / filename):
                raise ValueError(f"snapshot_existing_directory_conflict: {name}")
        for name in built:
            filename = manifest["plugins"][name]["artifact"]
            directory = Path(manifest["plugins"][name]["pluginPath"])
            if not directory.exists():
                (temporary / name).replace(directory)
            (temporary / filename).replace(output / filename)
        pending = temporary / "snapshots.json"
        pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pending.replace(output / "snapshots.json")
    return {"status": "packaged", "runtimeVerification": "pending", "manifest": str(output / "snapshots.json"),
            "built": built, "reused": reused}


def main() -> int:
    if sys.argv[1:2] == ["snapshots"]:
        parser = argparse.ArgumentParser(description="Build local complete plugin snapshots without account writes")
        parser.add_argument("output", type=Path)
        parser.add_argument("--project", type=Path, default=ROOT)
        args = parser.parse_args(sys.argv[2:])
        try:
            print(json.dumps(snapshots(args.project, args.output), ensure_ascii=False))
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            parser.exit(1, json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False) + "\n")
        return 0
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
