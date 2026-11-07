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


def _snapshot_files(project: Path, registry: dict) -> list[str]:
    paths = sorted({path for record in registry.values() for path in record["releaseInputs"]})
    return sorted(set(_git(project, "ls-files", "-z", "--cached", "--others",
                           "--exclude-standard", "--", *paths).split("\0")) - {""})


def _snapshot_inputs(project: Path, name: str, record: dict, source_files: list[str]) -> tuple[Path, list[Path], str]:
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
    for raw in source_files:
        relative = Path(raw)
        if not any(relative.is_relative_to(Path(source)) for source in paths):
            continue
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


def _snapshot_version(package: Path, name: str, *, cloud: bool = True) -> str:
    manifests = [json.loads((package / client / "plugin.json").read_text(encoding="utf-8"))
                 for client in (".codex-plugin", ".claude-plugin")]
    version = manifests[0].get("version")
    if cloud:
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


def snapshots(project: Path, output: Path, account_mode: str | None = None, release_ref: str | None = None) -> dict:
    """Build complete, local-only plugin archives; never publish or install."""
    if account_mode not in (None, "RELEASE"):
        raise ValueError("snapshot_account_mode_invalid")
    project, output = project.resolve(), output.resolve()
    flow = _release_flow(project)
    commit = _git(project, "rev-parse", "HEAD").strip()
    dirty = bool(_git(project, "status", "--porcelain"))
    if account_mode == "RELEASE":
        if not release_ref:
            raise ValueError("snapshot_release_ref_required")
        tag = flow.validate_release_tag(release_ref.removeprefix("refs/tags/"))
        release_ref = "refs/tags/" + tag
        if dirty or _git(project, "rev-parse", "--verify", release_ref + "^{commit}").strip() != commit:
            raise ValueError("snapshot_release_source_unverified")
    elif release_ref is not None:
        raise ValueError("snapshot_release_ref_requires_account_release")
    repository = flow.github_repository_identity(project)
    registry = {name: record | {"snapshotRepository": repository} for name, record in flow.PLUGIN_REGISTRY.items()}
    if account_mode is not None:
        registry = {name: record | {"snapshotAccountMode": account_mode, "snapshotReleaseRef": release_ref} for name, record in registry.items()}
    source_files = _snapshot_files(project, registry)
    inputs = {name: _snapshot_inputs(project, name, record, source_files) for name, record in registry.items()}
    if any(output.is_relative_to(project / root) for root, _files, _digest in inputs.values()):
        raise ValueError("snapshot_output_inside_release_input")
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
            if (saved.get("inputVersion") == digest
                    and (account_mode != "RELEASE" or (saved.get("sourceCommit") == commit
                         and saved.get("releaseRef") == release_ref and saved.get("sourceDirty") is False))):
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
                    package_relative = relative.relative_to(root)
                    # Account uploads contain one plugin; npm packages retain their local markets.
                    if (account_mode == "RELEASE" and record.get("releaseShape") == "npm"
                            and package_relative.as_posix() in (
                                ".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json")):
                        continue
                    destination = package / package_relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(project / relative, destination)
            if record.get("commandTool") or record.get("releaseShape") == "npm":
                # Older release registries identify these packages by shape only.
                package_name = (record["commandTool"]["package"] if record.get("commandTool")
                                else json.loads((package / "package.json").read_text(encoding="utf-8"))["name"])
                if not isinstance(package_name, str) or not package_name.strip():
                    raise ValueError(f"invalid_package_name: {package}")
                _inject_management(package, package_name,
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
            if account_mode is not None:
                manifest["plugins"][name].update(accountMode=account_mode, packageName=name, releaseRef=release_ref)
            built.append(name)
        # A concurrent source edit must not publish a manifest for mixed inputs.
        source_files = _snapshot_files(project, registry)
        if any(_snapshot_inputs(project, name, record, source_files)[2] != inputs[name][2]
               for name, record in registry.items()):
            raise ValueError("snapshot_inputs_changed_during_build")
        if account_mode == "RELEASE" and (_git(project, "rev-parse", "HEAD").strip() != commit
                                          or _git(project, "rev-parse", "--verify", release_ref + "^{commit}").strip() != commit
                                          or _git(project, "status", "--porcelain")):
            raise ValueError("snapshot_release_source_changed_during_build")
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


def development_packages(project: Path) -> list[Path]:
    """Prepare the existing local markets' complete command packages, without network or installation."""
    project = project.resolve()
    output = project / ".local/dev-plugin-packages"
    flow = _release_flow(project)
    records = {name: record for name, record in flow.PLUGIN_REGISTRY.items() if record.get("commandTool")}
    if output.parent.is_symlink() or (hasattr(output.parent, "is_junction") and output.parent.is_junction()):
        raise ValueError("development_parent_link")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink() or (hasattr(output, "is_junction") and output.is_junction()):
        raise ValueError("development_output_link")
    if output.exists():
        if (not (output / ".development-packages.json").is_file()
                or set(p.name for p in output.iterdir()) != set(records) | {".development-packages.json"}):
            raise ValueError("development_output_unmanaged")
        for name in records:
            package = output / name
            proof = json.loads((package / ".development-package.json").read_text(encoding="utf-8"))
            actual = {}
            for path in package.rglob("*"):
                if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                    raise ValueError("development_output_link")
                if path.is_file() and path.name != ".development-package.json" and "__pycache__" not in path.parts and path.suffix != ".pyc":
                    actual[path.relative_to(package).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != proof.get("files"):
                raise ValueError("development_output_modified; preserve user changes")
    lock = output.parent / ".dev-plugin-packages.lock"
    with lock.open("x") as lease:
        owned = os.fstat(lease.fileno())
        try:
            with tempfile.TemporaryDirectory(prefix=".dev-plugin-packages-", dir=output.parent) as temporary:
                staged = Path(temporary) / "packages"
                staged.mkdir()
                prepared = []
                for name, record in records.items():
                    source = project / record["releaseInputs"][0]
                    _validate_package(source, record["commandTool"]["package"])
                    spec = importlib.util.spec_from_file_location("dev_package_" + name.replace("-", "_"), source / "python/management.py")
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[spec.name] = module
                    spec.loader.exec_module(module)
                    files = module._development_package_files(project, source)
                    proof = {"format": 1, "sourceRoot": str(project), "packageDirectory": source.relative_to(project).as_posix(),
                             "implementationIdentity": module._implementation_identity_for_package(source),
                             "files": module._development_file_hashes(files)}
                    package = staged / name
                    for relative, content in files.items():
                        target = package / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(content)
                        original = source / relative
                        if original.is_file(): target.chmod(original.stat().st_mode & 0o777)
                    (package / module.DEVELOPMENT_PROOF).write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
                    _snapshot_version(package, name, cloud=False)
                    prepared.append((module, source, files))
                if any(module._development_package_files(project, source) != files for module, source, files in prepared):
                    raise ValueError("development_inputs_changed_during_build")
                (staged / ".development-packages.json").write_text(json.dumps(sorted(records)) + "\n", encoding="utf-8")
                # Recovery must outlive the temporary directory if Windows refuses both renames.
                previous = output.with_name(Path(temporary).name + "-recovery")
                if output.exists(): output.replace(previous)
                try:
                    staged.replace(output)
                except OSError as publish_error:
                    if previous.exists():
                        try:
                            previous.replace(output)
                        except OSError as restore_error:
                            raise ValueError(f"development_restore_failed: {publish_error}; {restore_error}; retained={previous}") from restore_error
                    raise
                if previous.exists():
                    try:
                        shutil.rmtree(previous)
                    except OSError as error:
                        print(f"development_cleanup_pending: retained={previous}: {error}", file=sys.stderr)
            return [output / name for name in records]
        finally:
            lease.close()
            current = lock.stat()
            if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino): lock.unlink()


def main() -> int:
    if sys.argv[1:2] == ["snapshots"]:
        parser = argparse.ArgumentParser(description="Build local complete plugin snapshots without account writes")
        parser.add_argument("output", type=Path)
        parser.add_argument("--project", type=Path, default=ROOT)
        parser.add_argument("--account-mode", choices=("RELEASE",), help="explicit cloud release account package")
        parser.add_argument("--release-ref", help="existing published release tag for the supplied clean source tree")
        args = parser.parse_args(sys.argv[2:])
        try:
            print(json.dumps(snapshots(args.project, args.output, args.account_mode, args.release_ref), ensure_ascii=False))
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
