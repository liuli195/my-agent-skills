"""Complete, check-local npm baselines; mutable installations are private copies."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PACK = REPO_ROOT / "plugins" / "tool-lifecycle" / "pack.py"
CANDIDATES_ENV = "OWN_SKILLS_NPM_CANDIDATES"
PACKAGE_DIRECTORIES = {"myspec": "my-spec", "build-and-verify": "build-and-verify"}
TARBALL_ENV = {"myspec": "MYSPEC_TEST_TARBALL", "build-and-verify": "BUILD_AND_VERIFY_TEST_TARBALL"}


@dataclass(frozen=True)
class NpmCandidate:
    name: str
    content_sha256: str
    tarball: Path
    prefix: Path
    npm: str

    @property
    def package_name(self) -> str:
        return f"@liuli195/{self.name}"

    @property
    def installed_package(self) -> Path:
        modules = "node_modules" if os.name == "nt" else "lib/node_modules"
        return self.prefix / modules / "@liuli195" / self.name

    @property
    def executable(self) -> Path:
        return self.prefix / (f"{self.name}.cmd" if os.name == "nt" else f"bin/{self.name}")


_candidates: dict[tuple[str, str], NpmCandidate] = {}
_validated: dict[NpmCandidate, tuple[int, int]] = {}


def _run(command: list[str]) -> str:
    shell = os.name == "nt" and command[0].lower().endswith((".cmd", ".bat"))
    result = subprocess.run(
        subprocess.list2cmdline(command) if shell else command,
        cwd=REPO_ROOT, text=True, capture_output=True, check=False, shell=shell,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or result.returncode
        raise RuntimeError(f"npm_candidate_preparation_failed: {detail}")
    return result.stdout.strip()


def _resources(name: str) -> dict[str, bytes]:
    source = REPO_ROOT / "plugins" / PACKAGE_DIRECTORIES[name]
    manifest = json.loads((source / "package.json").read_text(encoding="utf-8"))
    profile = json.loads((source / "python/lifecycle_profile.json").read_text(encoding="utf-8"))
    required = {"package.json", "python/management.py", "python/lifecycle_profile.json",
                f"python/{profile['PRIMARY_MODULE']}", ".agents/plugins/marketplace.json",
                ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"}
    required.update(str(path).removeprefix("./") for path in manifest["bin"].values())
    required.update(f"skills/{skill}/SKILL.md" for skill in profile["SKILL_NAMES"])
    for pattern in manifest["files"]:
        for match in source.glob(pattern):
            paths = match.rglob("*") if match.is_dir() else (match,)
            required.update(path.relative_to(source).as_posix() for path in paths
                            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    resources = {relative: (source / relative).read_bytes() for relative in required if relative != "python/management.py"}
    resources["python/management.py"] = PACK.with_name("python").joinpath("management.py").read_bytes()
    return resources


def _validate_basics(candidate: NpmCandidate) -> None:
    if candidate.name not in PACKAGE_DIRECTORIES:
        raise ValueError(f"unknown_npm_candidate: {candidate.name}")
    if not candidate.tarball.is_file():
        raise ValueError(f"missing_npm_candidate_tarball: {candidate.tarball}")
    if not candidate.executable.is_file() or not candidate.executable.resolve().is_relative_to(candidate.prefix.resolve()):
        raise ValueError(f"missing_npm_candidate_entrypoint: {candidate.executable}")
    manifest = json.loads((candidate.installed_package / "package.json").read_text(encoding="utf-8"))
    if manifest.get("name") != candidate.package_name:
        raise ValueError(f"wrong_npm_candidate_install: {candidate.installed_package}")


def _validate(candidate: NpmCandidate, resources: dict[str, bytes] | None = None) -> None:
    _validate_basics(candidate)
    if hashlib.sha256(candidate.tarball.read_bytes()).hexdigest() != candidate.content_sha256:
        raise ValueError(f"changed_npm_candidate: {candidate.tarball}")
    with tarfile.open(candidate.tarball, "r:gz") as archive:
        manifest_file = archive.extractfile("package/package.json")
        if manifest_file is None:
            raise ValueError("missing_npm_candidate_manifest")
        manifest = json.load(manifest_file)
        if manifest.get("name") != candidate.package_name:
            raise ValueError(f"wrong_npm_candidate_package: {candidate.tarball}")
        for member in archive.getmembers():
            if not member.isfile():
                continue
            relative = Path(member.name).relative_to("package")
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"unsafe_npm_candidate_resource: {member.name}")
            packed = archive.extractfile(member)
            if packed is None or (candidate.installed_package / relative).read_bytes() != packed.read():
                raise ValueError(f"incomplete_npm_candidate_install: {relative}")
        for relative, expected in (resources or {}).items():
            packed = archive.extractfile(f"package/{relative}")
            if packed is None or packed.read() != expected:
                raise ValueError(f"missing_or_stale_npm_candidate_resource: {relative}")


def _require_candidate(candidate: NpmCandidate) -> None:
    _validate_basics(candidate)
    status = candidate.tarball.stat()
    stamp = (status.st_size, status.st_mtime_ns)
    if candidate not in _validated:
        _validate(candidate)
        _validated[candidate] = stamp
    elif _validated[candidate] != stamp:
        raise ValueError(f"changed_npm_candidate: {candidate.tarball}")


def _writable(root: Path) -> None:
    for path in (root, *root.rglob("*")):
        if not path.is_symlink():
            path.chmod(path.stat().st_mode | stat.S_IWUSR)


def remove_owned_candidate(root: Path) -> None:
    """Only call for a root created by this check, never a supplied tarball."""
    _writable(root)
    shutil.rmtree(root)


def prepare_candidate(name: str, owned_root: Path, *, tarball: Path | None = None) -> NpmCandidate:
    resources = _resources(name)
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("missing_command: npm")
    owned_root.mkdir()
    try:
        if tarball is None:
            tarball = Path(_run([sys.executable, str(PACK), name, str(owned_root / "package")]))
        else:
            supplied = tarball.expanduser().resolve(strict=True)
            package = owned_root / "package"
            package.mkdir()
            tarball = package / supplied.name
            shutil.copy2(supplied, tarball)
        prefix = owned_root / "prefix"
        _run([npm, "install", "--global", "--prefix", str(prefix), "--ignore-scripts",
              "--no-audit", "--no-fund", str(tarball)])
        candidate = NpmCandidate(name, hashlib.sha256(tarball.read_bytes()).hexdigest(), tarball, prefix, npm)
        _validate(candidate, resources)
        for path in (*owned_root.rglob("*"), owned_root):
            if not path.is_symlink():
                path.chmod(path.stat().st_mode & ~0o222)
        status = tarball.stat()
        _validated[candidate] = (status.st_size, status.st_mtime_ns)
        return candidate
    except BaseException as error:
        try:
            remove_owned_candidate(owned_root)
        except OSError as cleanup_error:
            error.add_note(f"npm_candidate_cleanup_failed: {owned_root}: {cleanup_error}")
        raise


def candidate_environment(candidates: dict[str, NpmCandidate]) -> str:
    return json.dumps({name: {key: str(value) for key, value in asdict(candidate).items()}
                       for name, candidate in candidates.items()})


def candidate_for(name: str) -> NpmCandidate:
    try:
        environment = os.environ[CANDIDATES_ENV]
        key = (environment, name)
        candidate = _candidates.get(key)
        if candidate is None:
            value = json.loads(environment)[name]
            candidate = NpmCandidate(**{**value, "tarball": Path(value["tarball"]), "prefix": Path(value["prefix"])})
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"npm_candidate_not_prepared_by_controller: {name}") from error
    if candidate.name != name:
        raise ValueError(f"wrong_npm_candidate_identity: {name}")
    _require_candidate(candidate)
    _candidates[key] = candidate
    return candidate


def copy_install(candidate: NpmCandidate, private_prefix: Path) -> tuple[Path, Path]:
    """Return (executable, installed_package) in a new, writable private prefix."""
    _require_candidate(candidate)
    private_prefix.mkdir()
    try:
        shutil.copytree(candidate.prefix, private_prefix, symlinks=True, dirs_exist_ok=True)
        _writable(private_prefix)
        private = NpmCandidate(candidate.name, candidate.content_sha256, candidate.tarball, private_prefix, candidate.npm)
        _validate_basics(private)
        return private.executable, private.installed_package
    except BaseException as error:
        try:
            remove_owned_candidate(private_prefix)
        except OSError as cleanup_error:
            error.add_note(f"npm_candidate_copy_cleanup_failed: {private_prefix}: {cleanup_error}")
        raise
