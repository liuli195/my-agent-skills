"""Release Flow Plugin（发布流程插件）命令行入口。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"

FORBIDDEN_VARIABLE_VALUE_KEYS = {"value", "secret", "defaultValue", "default_value"}
SUPPORTED_VARIABLE_SOURCE = "github-actions-variable"
SUPPORTED_TRANSFORM_TYPE = "json-env"
SUPPORTED_GENERATOR_TYPE = "codex-marketplace"
SUPPORTED_GENERATOR_IDENTITY = "codex"
PLUGIN_REGISTRY: dict[str, dict[str, Any]] = {
    "agent-guard": {
        "manifests": [
            "plugins/agent-guard/.codex-plugin/plugin.json",
            "plugins/agent-guard/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "agent-guard",
            "source": {"source": "local", "path": "./plugins/agent-guard"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        },
    },
    "release-flow": {
        "manifests": [
            "plugins/release-flow/.codex-plugin/plugin.json",
            "plugins/release-flow/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "release-flow",
            "source": {"source": "local", "path": "./plugins/release-flow"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
    "cross-agent-review": {
        "manifests": [
            "plugins/cross-agent-review/.codex-plugin/plugin.json",
            "plugins/cross-agent-review/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "cross-agent-review",
            "source": {"source": "local", "path": "./plugins/cross-agent-review"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
    "pr-flow": {
        "manifests": [
            "plugins/pr-flow/.codex-plugin/plugin.json",
            "plugins/pr-flow/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "pr-flow",
            "source": {"source": "local", "path": "./plugins/pr-flow"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
    "build-and-verify": {
        "manifests": [
            "plugins/build-and-verify/.codex-plugin/plugin.json",
            "plugins/build-and-verify/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "build-and-verify",
            "source": {"source": "local", "path": "./plugins/build-and-verify"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
}
BUILD_AND_VERIFY_PLUGIN = "build-and-verify"
BUILD_AND_VERIFY_CONFIG_FILE = Path(".build-and-verify/config.json")
BUILD_AND_VERIFY_RUNTIME_VERSION_FILE = Path(".build-and-verify/runtime/version.json")
BUILD_AND_VERIFY_UPDATE_SCRIPT = Path(
    "plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py"
)
SETUP_TARGETS = [
    ("release-flow/config.yaml", ".release-flow/config.yaml"),
    ("release-flow/projection.yaml", ".release-flow/projection.yaml"),
    ("github/workflows/release.yml", ".github/workflows/release.yml"),
]


@dataclass(frozen=True)
class FlowConfig:
    path: Path
    version: int
    release_source_ref: str
    release_channel_branch: str
    release_branch_mode: str
    workflow_file: str
    workflow_trigger: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class ProjectionVariable:
    name: str
    source: str
    required: bool
    raw: dict[str, Any]


@dataclass(frozen=True)
class ProjectionCodexIdentity:
    marketplace_name: str
    display_name: str


@dataclass(frozen=True)
class ProjectionClaudeIdentity:
    marketplace_name: str
    owner_name: str


@dataclass(frozen=True)
class ProjectionIdentity:
    codex: ProjectionCodexIdentity
    claude: ProjectionClaudeIdentity


@dataclass(frozen=True)
class ProjectionTransform:
    path: Path
    type: str
    set: dict[str, str]


@dataclass(frozen=True)
class ProjectionGenerator:
    path: Path
    type: str
    identity: str
    plugins: list[str]


@dataclass(frozen=True)
class Projection:
    path: Path
    version: int
    identity: ProjectionIdentity | None
    variables: dict[str, ProjectionVariable]
    generators: list[ProjectionGenerator]
    transforms: list[ProjectionTransform]
    raw: dict[str, Any]


def run_setup(args: argparse.Namespace) -> int:
    if not args.authorize_project_files:
        print("status: dry_run")
        print(f"project: {args.project}")
        for _template, target in SETUP_TARGETS:
            print(f"would_write: {target}")
        return 0

    for template, target in SETUP_TARGETS:
        target_path = args.project / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text((TEMPLATE_ROOT / template).read_text(encoding="utf-8"), encoding="utf-8")

    print("status: setup_complete")
    print(f"project: {args.project}")
    return 0


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing_file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid_yaml: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"invalid_yaml_mapping: {path}")
    return data


def is_relative_path_inside_project(path: Path) -> bool:
    if path.is_absolute():
        return False
    return ".." not in path.parts


def resolve_project_path(project: Path, relative_path: Path, error_prefix: str) -> Path:
    if not is_relative_path_inside_project(relative_path):
        raise ValueError(f"{error_prefix}: {relative_path}")
    project_root = project.resolve()
    target_path = (project_root / relative_path).resolve()
    if target_path != project_root and project_root not in target_path.parents:
        raise ValueError(f"{error_prefix}: {relative_path}")
    return target_path


def validate_release_tag(tag: str) -> str:
    tag_path = Path(tag)
    if tag_path.is_absolute() or tag in {"", ".", ".."} or tag.startswith("-"):
        raise ValueError(f"invalid_release_tag: {tag}")
    if "/" in tag or "\\" in tag or ".." in tag_path.parts:
        raise ValueError(f"invalid_release_tag: {tag}")
    return tag


def read_config(project: Path) -> FlowConfig:
    path = project / ".release-flow" / "config.yaml"
    data = load_yaml_mapping(path)
    if "records" in data:
        raise ValueError("invalid_config: records is no longer supported")
    if "manifests" in data:
        raise ValueError("invalid_config: manifests.versionFiles is no longer supported")
    github = data.get("github", {})
    if isinstance(github, dict) and "rulesets" in github:
        raise ValueError("invalid_config: github.rulesets is no longer supported")
    version = data.get("version")
    if not isinstance(version, int):
        raise ValueError("config_version_invalid")
    release = data.get("release")
    if not isinstance(release, dict):
        raise ValueError("invalid_config: release must be mapping")
    release_source_ref = release.get("sourceRef")
    if not isinstance(release_source_ref, str):
        raise ValueError("invalid_config: release.sourceRef must be string")
    release_channel_branch = release.get("channelBranch")
    if not isinstance(release_channel_branch, str):
        raise ValueError("invalid_config: release.channelBranch must be string")
    release_branch_mode = release.get("branchMode")
    if release_branch_mode != "remote-only":
        raise ValueError("invalid_config: release.branchMode must be remote-only")

    workflow = data.get("workflow")
    if not isinstance(workflow, dict):
        raise ValueError("invalid_config: workflow must be mapping")
    workflow_file = workflow.get("file")
    if not isinstance(workflow_file, str):
        raise ValueError("invalid_config: workflow.file must be string")
    workflow_trigger = workflow.get("trigger")
    if workflow_trigger != "workflow_dispatch":
        raise ValueError("invalid_config: workflow.trigger must be workflow_dispatch")

    return FlowConfig(
        path=path,
        version=version,
        release_source_ref=release_source_ref,
        release_channel_branch=release_channel_branch,
        release_branch_mode=release_branch_mode,
        workflow_file=workflow_file,
        workflow_trigger=workflow_trigger,
        raw=data,
    )


def require_string(data: dict[str, Any], key: str, error: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(error)
    return value


def read_projection_identity(data: dict[str, Any]) -> ProjectionIdentity | None:
    identity_data = data.get("identity")
    if identity_data is None:
        return None
    if not isinstance(identity_data, dict):
        raise ValueError("projection_identity_invalid")

    codex_data = identity_data.get("codex")
    if not isinstance(codex_data, dict):
        raise ValueError("projection_identity_codex_invalid")
    claude_data = identity_data.get("claude")
    if not isinstance(claude_data, dict):
        raise ValueError("projection_identity_claude_invalid")
    if "releaseFlowPlugin" in identity_data:
        raise ValueError("projection_identity_release_flow_plugin_unsupported")

    return ProjectionIdentity(
        codex=ProjectionCodexIdentity(
            marketplace_name=require_string(
                codex_data,
                "marketplaceName",
                "projection_identity_missing: identity.codex.marketplaceName",
            ),
            display_name=require_string(
                codex_data,
                "displayName",
                "projection_identity_missing: identity.codex.displayName",
            ),
        ),
        claude=ProjectionClaudeIdentity(
            marketplace_name=require_string(
                claude_data,
                "marketplaceName",
                "projection_identity_missing: identity.claude.marketplaceName",
            ),
            owner_name=require_string(
                claude_data,
                "ownerName",
                "projection_identity_missing: identity.claude.ownerName",
            ),
        ),
    )


def read_projection(project: Path) -> Projection:
    path = project / ".release-flow" / "projection.yaml"
    data = load_yaml_mapping(path)
    version = data.get("version")
    if not isinstance(version, int):
        raise ValueError("projection_version_invalid")
    identity = read_projection_identity(data)

    variables_data = data.get("variables", {})
    if not isinstance(variables_data, dict):
        raise ValueError("projection_variables_invalid")
    variables: dict[str, ProjectionVariable] = {}
    for name, variable_data in variables_data.items():
        if not isinstance(name, str) or not isinstance(variable_data, dict):
            raise ValueError("projection_variable_invalid")
        source = variable_data.get("source")
        if not isinstance(source, str):
            raise ValueError(f"projection_variable_source_missing: {name}")
        required = variable_data.get("required", False)
        if not isinstance(required, bool):
            raise ValueError(f"projection_variable_required_invalid: {name}")
        variables[name] = ProjectionVariable(
            name=name,
            source=source,
            required=required,
            raw=variable_data,
        )

    generators_data = data.get("generators", [])
    if not isinstance(generators_data, list):
        raise ValueError("projection_generators_invalid")
    generators: list[ProjectionGenerator] = []
    for generator_data in generators_data:
        if not isinstance(generator_data, dict):
            raise ValueError("projection_generator_invalid")
        generator_path = generator_data.get("path")
        generator_type = generator_data.get("type")
        generator_identity = generator_data.get("identity")
        plugins_data = generator_data.get("plugins", [])
        if not isinstance(generator_path, str):
            raise ValueError("projection_generator_path_invalid")
        generator_relative_path = Path(generator_path)
        resolve_project_path(project, generator_relative_path, "invalid_projection_generator_path")
        if not isinstance(generator_type, str):
            raise ValueError(f"projection_generator_type_missing: {generator_path}")
        if not isinstance(generator_identity, str):
            raise ValueError(f"projection_generator_identity_missing: {generator_path}")
        if not isinstance(plugins_data, list) or not all(
            isinstance(plugin_name, str) for plugin_name in plugins_data
        ):
            raise ValueError(f"projection_generator_plugins_invalid: {generator_path}")
        generators.append(
            ProjectionGenerator(
                path=generator_relative_path,
                type=generator_type,
                identity=generator_identity,
                plugins=list(plugins_data),
            )
        )

    transforms_data = data.get("transforms", [])
    if not isinstance(transforms_data, list):
        raise ValueError("projection_transforms_invalid")
    transforms: list[ProjectionTransform] = []
    for transform_data in transforms_data:
        if not isinstance(transform_data, dict):
            raise ValueError("projection_transform_invalid")
        transform_path = transform_data.get("path")
        transform_type = transform_data.get("type")
        set_data = transform_data.get("set", {})
        if not isinstance(transform_path, str):
            raise ValueError("projection_transform_path_invalid")
        transform_relative_path = Path(transform_path)
        resolve_project_path(project, transform_relative_path, "invalid_projection_transform_path")
        if not isinstance(transform_type, str):
            raise ValueError(f"projection_transform_type_missing: {transform_path}")
        if not isinstance(set_data, dict) or not all(
            isinstance(pointer, str) and isinstance(variable, str)
            for pointer, variable in set_data.items()
        ):
            raise ValueError(f"projection_transform_set_invalid: {transform_path}")
        transforms.append(
            ProjectionTransform(
                path=transform_relative_path,
                type=transform_type,
                set=dict(set_data),
            )
        )

    return Projection(
        path=path,
        version=version,
        identity=identity,
        variables=variables,
        generators=generators,
        transforms=transforms,
        raw=data,
    )


def projection_identity_value(projection: Projection, reference: str) -> str:
    if projection.identity is None:
        raise ValueError(f"projection_identity_reference_unknown: {reference}")
    values = {
        "identity.codex.marketplaceName": projection.identity.codex.marketplace_name,
        "identity.codex.displayName": projection.identity.codex.display_name,
        "identity.claude.marketplaceName": projection.identity.claude.marketplace_name,
        "identity.claude.ownerName": projection.identity.claude.owner_name,
    }
    try:
        return values[reference]
    except KeyError as exc:
        raise ValueError(f"projection_identity_reference_unknown: {reference}") from exc


def expected_variable_value(projection: Projection, variable: ProjectionVariable) -> str | None:
    expected = variable.raw.get("expected")
    if expected is None:
        return None
    if not isinstance(expected, str):
        raise ValueError(f"projection_variable_expected_invalid: {variable.name}")
    return projection_identity_value(projection, expected)


def projection_errors(projection: Projection) -> list[str]:
    errors: list[str] = []
    for variable in projection.variables.values():
        if variable.source != SUPPORTED_VARIABLE_SOURCE:
            errors.append(f"projection_variable_source_unsupported: {variable.name}")
        if FORBIDDEN_VARIABLE_VALUE_KEYS.intersection(variable.raw):
            errors.append(f"projection_variable_value_forbidden: {variable.name}")
        if "expected" in variable.raw:
            try:
                expected_variable_value(projection, variable)
            except ValueError as exc:
                errors.append(str(exc))
    for generator in projection.generators:
        if generator.type != SUPPORTED_GENERATOR_TYPE:
            errors.append(f"projection_generator_type_unsupported: {generator.path}")
        if generator.identity != SUPPORTED_GENERATOR_IDENTITY:
            errors.append(f"projection_generator_identity_unsupported: {generator.path}")
        if projection.identity is None:
            errors.append(f"projection_generator_identity_missing: {generator.path}")
        for plugin_name in generator.plugins:
            if plugin_name not in PLUGIN_REGISTRY:
                errors.append(f"projection_generator_plugin_unknown: {plugin_name}")
    for transform in projection.transforms:
        if transform.type != SUPPORTED_TRANSFORM_TYPE:
            errors.append(f"projection_transform_type_unsupported: {transform.path}")
        for pointer, reference in transform.set.items():
            try:
                projection_identity_value(projection, reference)
            except ValueError as exc:
                errors.append(str(exc))
            if not pointer.startswith("/"):
                errors.append(f"projection_transform_pointer_invalid: {pointer}")
    return errors


def validate_project(project: Path) -> list[str]:
    try:
        read_config(project)
        projection = read_projection(project)
    except ValueError as exc:
        return [str(exc)]
    return projection_errors(projection)


def run_validate(args: argparse.Namespace) -> int:
    errors = validate_project(args.project)
    if errors:
        print("status: issues")
        for error in errors:
            print(f"error: {error}")
        return 1
    print("status: verified")
    return 0


def read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing_file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid_json: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"invalid_json_mapping: {path}")
    return data


def json_pointer_parts(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise ValueError(f"json_pointer_invalid: {pointer}")
    if pointer == "/":
        return [""]
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def json_pointer_list_index(part: str, pointer: str) -> int:
    if not part.isdecimal():
        raise ValueError(f"json_pointer_list_index_invalid: {pointer}")
    return int(part)


def json_pointer_child(target: Any, part: str, pointer: str) -> Any:
    if isinstance(target, dict):
        if part not in target:
            raise ValueError(f"json_pointer_parent_missing: {pointer}")
        return target[part]
    if isinstance(target, list):
        index = json_pointer_list_index(part, pointer)
        try:
            return target[index]
        except IndexError as exc:
            raise ValueError(f"json_pointer_parent_missing: {pointer}") from exc
    raise ValueError(f"json_pointer_parent_invalid: {pointer}")


def set_json_pointer_value(target: Any, part: str, pointer: str, value: Any) -> None:
    if isinstance(target, dict):
        target[part] = value
        return
    if isinstance(target, list):
        index = json_pointer_list_index(part, pointer)
        try:
            target[index] = value
        except IndexError as exc:
            raise ValueError(f"json_pointer_target_missing: {pointer}") from exc
        return
    raise ValueError(f"json_pointer_parent_invalid: {pointer}")


def set_json_pointer(data: dict[str, Any], pointer: str, value: Any) -> None:
    parts = json_pointer_parts(pointer)
    target: Any = data
    for part in parts[:-1]:
        target = json_pointer_child(target, part, pointer)
    set_json_pointer_value(target, parts[-1], pointer, value)


def codex_marketplace_entry(plugin_name: str) -> dict[str, Any]:
    try:
        return dict(PLUGIN_REGISTRY[plugin_name]["codexMarketplace"])
    except KeyError as exc:
        raise ValueError(f"projection_generator_plugin_unknown: {plugin_name}") from exc


def generate_codex_marketplace(
    projection: Projection, generator: ProjectionGenerator
) -> dict[str, Any]:
    if projection.identity is None:
        raise ValueError(f"projection_generator_identity_missing: {generator.path}")
    if generator.type != SUPPORTED_GENERATOR_TYPE:
        raise ValueError(f"projection_generator_type_unsupported: {generator.path}")
    if generator.identity != SUPPORTED_GENERATOR_IDENTITY:
        raise ValueError(f"projection_generator_identity_unsupported: {generator.path}")
    return {
        "name": projection.identity.codex.marketplace_name,
        "interface": {"displayName": projection.identity.codex.display_name},
        "plugins": [codex_marketplace_entry(plugin_name) for plugin_name in generator.plugins],
    }


def apply_projection_generator(
    project: Path, projection: Projection, generator: ProjectionGenerator
) -> None:
    target_path = resolve_project_path(project, generator.path, "invalid_projection_generator_path")
    target = generate_codex_marketplace(projection, generator)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_json_env_transform(project: Path, projection: Projection, transform: ProjectionTransform) -> None:
    target_path = resolve_project_path(project, transform.path, "invalid_projection_transform_path")
    target = read_json_mapping(target_path)
    for pointer, reference in transform.set.items():
        set_json_pointer(target, pointer, projection_identity_value(projection, reference))
    target_path.write_text(json.dumps(target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_project(args: argparse.Namespace) -> int:
    errors = validate_project(args.project)
    if errors:
        print("status: issues")
        for error in errors:
            print(f"error: {error}")
        return 1
    try:
        projection = read_projection(args.project)
        apply_projection(args.project, projection)
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1
    print("status: projected")
    return 0


def github_config_value(config: FlowConfig, path: list[str], default: Any) -> Any:
    value: Any = config.raw.get("github", {})
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def run_github_plan(args: argparse.Namespace) -> int:
    try:
        config = read_config(args.project)
        projection = read_projection(args.project)
        errors = projection_errors(projection)
        if errors:
            raise ValueError(errors[0])
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    workflow_permissions = github_config_value(
        config, ["actions", "workflowPermissions"], "read-and-write"
    )

    print("status: github_plan")
    print(f"actions_workflow_permissions: {workflow_permissions}")
    return 0


def run_configure_github(args: argparse.Namespace) -> int:
    if not args.dry_run and not args.authorize_github:
        print("status: issues")
        print("error: configure_github_requires_authorize_github")
        return 2

    try:
        config = read_config(args.project)
        projection = read_projection(args.project)
        errors = projection_errors(projection)
        if errors:
            raise ValueError(errors[0])
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    workflow_permissions = github_config_value(
        config, ["actions", "workflowPermissions"], "read-and-write"
    )
    if args.dry_run:
        print("status: manual_steps")
        print(f"project: {args.project}")
        print(f"Set Actions workflow permissions to {workflow_permissions}")
        return 0

    print("status: issues")
    print("error: github_write_not_available_without_repository_context")
    return 2


def tag_version(tag: str) -> str:
    validate_release_tag(tag)
    if tag.startswith("v") and len(tag) > 1:
        return tag[1:]
    return tag


def parse_bump_plugins(raw: str | list[str]) -> list[str]:
    values = raw if isinstance(raw, list) else [raw]
    if values == [""]:
        return []
    plugins = [item.strip() for value in values for item in value.split(",") if value != ""]
    if any(not item for item in plugins):
        raise ValueError("bump_plugins_invalid")
    for plugin_name in plugins:
        if plugin_name not in PLUGIN_REGISTRY:
            raise ValueError(f"plugin_unknown: {plugin_name}")
    return list(dict.fromkeys(plugins))


def plugin_manifest_paths(plugin_name: str) -> list[str]:
    try:
        manifests = PLUGIN_REGISTRY[plugin_name]["manifests"]
    except KeyError as exc:
        raise ValueError(f"plugin_unknown: {plugin_name}") from exc
    return [str(manifest) for manifest in manifests]


def manifest_version(project: Path, manifest_file: str) -> str:
    manifest_path = resolve_project_path(project, Path(manifest_file), "invalid_manifest_path")
    manifest = read_json_mapping(manifest_path)
    version = manifest.get("version")
    if not isinstance(version, str):
        raise ValueError(f"manifest_version_missing: {manifest_file}")
    return version


def build_and_verify_runtime_version(project: Path) -> str | None:
    if not (project / BUILD_AND_VERIFY_CONFIG_FILE).is_file():
        return None
    version_path = project / BUILD_AND_VERIFY_RUNTIME_VERSION_FILE
    if not version_path.is_file():
        return "missing"
    try:
        data = read_json_mapping(version_path)
    except ValueError:
        return "invalid"
    version = data.get("runtime_version") or data.get("plugin_version")
    return version if isinstance(version, str) and version else "missing"


def build_and_verify_runtime_update_error(project: Path, requested_version: str) -> str:
    runtime_version = build_and_verify_runtime_version(project)
    if runtime_version is None or runtime_version == requested_version:
        return ""
    return (
        "runtime_update_required: build-and-verify "
        f"runtime={runtime_version} requested={requested_version}"
    )


def git_output(project: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise ValueError(f"command_failed: git {' '.join(args)}: {output}")
    return result.stdout


def git_ref_exists(project: Path, ref: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--verify", ref],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def ensure_remote_branch(project: Path, branch: str) -> None:
    ref = f"origin/{branch}"
    if git_ref_exists(project, ref):
        return
    result = subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "fetch",
            "--depth=1",
            "origin",
            f"{branch}:refs/remotes/origin/{branch}",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise ValueError(f"remote_ref_missing: {ref}: {output}")


def remote_ref_manifest_version(project: Path, branch: str, manifest_file: str) -> str | None:
    ref = f"origin/{branch}"
    ensure_remote_branch(project, branch)
    result = subprocess.run(
        ["git", "-C", str(project), "show", f"{ref}:{manifest_file}"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    version = data.get("version")
    if not isinstance(version, str):
        raise ValueError(f"remote_manifest_version_missing: {manifest_file}")
    return version


def remote_manifest_version(project: Path, config: FlowConfig, manifest_file: str) -> str | None:
    return remote_ref_manifest_version(project, config.release_channel_branch, manifest_file)


def source_ref_manifest_version(project: Path, config: FlowConfig, manifest_file: str) -> str | None:
    return remote_ref_manifest_version(project, config.release_source_ref, manifest_file)


def apply_projection(project: Path, projection: Projection) -> None:
    for generator in projection.generators:
        apply_projection_generator(project, projection, generator)
    for transform in projection.transforms:
        apply_json_env_transform(project, projection, transform)


def marketplace_identity_value(data: dict[str, Any], pointer: str) -> Any:
    target: Any = data
    for part in json_pointer_parts(pointer):
        if not isinstance(target, dict) or part not in target:
            return None
        target = target[part]
    return target


def marketplace_identity_errors(root: Path, projection: Projection) -> list[str]:
    if projection.identity is None:
        return []
    checks = [
        (
            Path(".agents/plugins/marketplace.json"),
            {
                "/name": projection.identity.codex.marketplace_name,
                "/interface/displayName": projection.identity.codex.display_name,
            },
        ),
        (
            Path(".claude-plugin/marketplace.json"),
            {
                "/name": projection.identity.claude.marketplace_name,
                "/owner/name": projection.identity.claude.owner_name,
            },
        ),
    ]
    errors: list[str] = []
    for relative_path, expected_values in checks:
        path = root / relative_path
        if not path.exists():
            continue
        data = read_json_mapping(path)
        for pointer, expected_value in expected_values.items():
            actual_value = marketplace_identity_value(data, pointer)
            if actual_value != expected_value:
                errors.append(
                    "marketplace_identity_mismatch: "
                    f"{relative_path.as_posix()} {pointer} "
                    f"expected={expected_value} actual={actual_value}"
                )
    return errors


def ignored_expected_path(relative_path: Path) -> bool:
    ignored_parts = {".git", "__pycache__", ".pytest_cache"}
    if ignored_parts.intersection(relative_path.parts):
        return True
    return False


def git_tracked_files(project: Path) -> list[Path] | None:
    result = subprocess.run(
        ["git", "-C", str(project), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return [
        Path(item)
        for item in result.stdout.decode("utf-8").split("\0")
        if item
    ]


def copy_tracked_project_for_expected(source: Path, target: Path, tracked_files: list[Path]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for relative_path in tracked_files:
        if not is_relative_path_inside_project(relative_path) or ignored_expected_path(relative_path):
            continue
        source_path = source / relative_path
        if not source_path.is_file():
            continue
        target_path = target / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def copy_project_for_expected(source: Path, target: Path) -> None:
    tracked_files = git_tracked_files(source)
    if tracked_files is not None:
        copy_tracked_project_for_expected(source, target, tracked_files)
        return

    def ignore(directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in {".git", "__pycache__", ".pytest_cache"}}

    shutil.copytree(source, target, ignore=ignore)


def origin_url(project: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), "config", "--get", "remote.origin.url"],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def origin_is_github(project: Path) -> bool:
    url = origin_url(project).lower()
    if url.startswith("git@github.com:"):
        return True
    return urlparse(url).hostname == "github.com"


def remote_release_errors(project: Path, tag: str) -> list[str]:
    tag_result = subprocess.run(
        ["git", "-C", str(project), "ls-remote", "--tags", "origin", f"refs/tags/{tag}"],
        check=False,
        text=True,
        capture_output=True,
    )
    if tag_result.returncode != 0:
        return [f"remote_release_unknown: {tag}"]
    errors: list[str] = []
    if tag_result.stdout.strip():
        errors.append(f"release already exists: {tag}")
    if not origin_is_github(project):
        return errors
    try:
        gh_result = subprocess.run(
            ["gh", "release", "view", tag],
            cwd=project,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return [*errors, f"remote_release_unknown: {tag}"]
    gh_output = (gh_result.stderr or gh_result.stdout).lower()
    if gh_result.returncode == 0:
        errors.append(f"release already exists: {tag}")
    elif "not found" not in gh_output and "could not resolve" not in gh_output:
        errors.append(f"remote_release_unknown: {tag}")
    return errors


def preflight_errors(
    project: Path,
    tag: str,
    version: str,
    bump_plugins: list[str],
    config: FlowConfig,
    projection: Projection,
) -> list[str]:
    errors: list[str] = []
    expected_version = tag_version(tag)
    if version != expected_version:
        errors.append(f"release_version_mismatch: {tag}")

    projection_plugins = sorted({plugin for generator in projection.generators for plugin in generator.plugins})
    bumped = set(bump_plugins)
    for plugin_name in projection_plugins:
        if plugin_name not in PLUGIN_REGISTRY:
            errors.append(f"projection_generator_plugin_unknown: {plugin_name}")
            continue
        try:
            for manifest_file in plugin_manifest_paths(plugin_name):
                current = manifest_version(project, manifest_file)
                if plugin_name in bumped:
                    if current != version:
                        errors.append(f"manifest_version_mismatch: {manifest_file}")
                    source = source_ref_manifest_version(project, config, manifest_file)
                    if source != version:
                        errors.append(f"source_ref_requires_pr: {config.release_source_ref}: {manifest_file}")
                else:
                    remote = remote_manifest_version(project, config, manifest_file)
                    if remote is None or current != remote:
                        errors.append(f"plugin_requires_bump: {plugin_name}")
                        break
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))

    if BUILD_AND_VERIFY_PLUGIN in bumped:
        runtime_error = build_and_verify_runtime_update_error(project, version)
        if runtime_error:
            errors.append(runtime_error)

    if not errors:
        with tempfile.TemporaryDirectory(prefix="release-flow-preflight-") as temp_dir:
            expected_tree = Path(temp_dir) / "expected"
            copy_project_for_expected(project, expected_tree)
            expected_projection = read_projection(expected_tree)
            apply_projection(expected_tree, expected_projection)
            identity_errors = marketplace_identity_errors(expected_tree, expected_projection)
            if identity_errors:
                errors.extend(identity_errors)

    errors.extend(remote_release_errors(project, tag))
    return errors


def preflight_next_action(error: str, project: Path | None = None) -> str:
    if error.startswith("source_ref_requires_pr: "):
        return "create and merge the version bump through PR Flow, then rerun release-flow preflight"
    if error.startswith("manifest_version_mismatch: "):
        manifest_path = error.split(": ", 1)[1]
        return f"correct the manifest version in {manifest_path}, then rerun release-flow preflight"
    if error.startswith("release already exists: "):
        return (
            "requested release/tag already exists; choose the release version with the user and agent, "
            "then rerun release-flow preflight"
        )
    if error.startswith("runtime_update_required: "):
        project_arg = project if project is not None else Path(".")
        return (
            f"run python {BUILD_AND_VERIFY_UPDATE_SCRIPT.as_posix()} update-runtime "
            f"--project {project_arg}"
        )
    return ""


def preflight_summary_next_action(errors: list[str]) -> str:
    if len(errors) < 2:
        return ""

    tracked_prefixes = (
        "release already exists: ",
        "manifest_version_mismatch: ",
        "source_ref_requires_pr: ",
        "plugin_requires_bump: ",
    )
    if any(not error.startswith(tracked_prefixes) for error in errors):
        return ""

    states: list[str] = []
    actions: list[str] = []
    if any(error.startswith("release already exists: ") for error in errors):
        states.append("release/tag already exists")
        actions.append("choose the release version with the user and agent")
    if any(error.startswith("manifest_version_mismatch: ") for error in errors):
        states.append("manifest versions do not match requested release")
    if any(error.startswith("source_ref_requires_pr: ") for error in errors):
        states.append("source ref lacks version bump")
    if any(error.startswith("manifest_version_mismatch: ") for error in errors):
        actions.append("correct manifest versions through PR Flow")
    if any(error.startswith("source_ref_requires_pr: ") for error in errors):
        actions.append("create and merge the source-ref version bump through PR Flow")
    if any(error.startswith("plugin_requires_bump: ") for error in errors):
        states.append("some plugins need bumpPlugins")
        actions.append("include required plugins in bumpPlugins through PR Flow when they should ship")
    return f"current state: {'; '.join(states)}. handling path: {', '.join(actions)}, then rerun release-flow preflight"


def print_preflight_errors(errors: list[str], project: Path | None = None) -> None:
    for error in errors:
        print(f"error: {error}")
    summary_next_action = preflight_summary_next_action(errors)
    if summary_next_action:
        print(f"nextAction: {summary_next_action}")
        return
    for error in errors:
        next_action = preflight_next_action(error, project)
        if next_action:
            print(f"nextAction: {next_action}")


def run_preflight(args: argparse.Namespace) -> int:
    try:
        config = read_config(args.project)
        projection = read_projection(args.project)
        errors = projection_errors(projection)
        if errors:
            raise ValueError(errors[0])
        bump_plugins = parse_bump_plugins(args.bump_plugins)
        errors = preflight_errors(
            args.project,
            args.tag,
            args.version,
            bump_plugins,
            config,
            projection,
        )
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    if errors:
        print("status: issues")
        print_preflight_errors(errors, args.project)
        return 1

    print("status: preflight_passed")
    print(f"release_tag: {args.tag}")
    print(f"version: {args.version}")
    print(f"bumpPlugins: {','.join(bump_plugins)}")
    return 0


DEFAULT_GH_WORKFLOW_RUN_RETRIES = 3


def workflow_dispatch_args(config: FlowConfig, tag: str, version: str, bump_plugins: list[str]) -> list[str]:
    validate_release_tag(tag)
    return [
        shutil.which("gh") or "gh",
        "workflow",
        "run",
        config.workflow_file,
        "--ref",
        config.release_source_ref,
        "-f",
        f"tag={tag}",
        "-f",
        f"version={version}",
        "-f",
        f"bumpPlugins={','.join(bump_plugins)}",
    ]


def gh_transient_eof(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode != 0 and "eof" in f"{result.stdout}\n{result.stderr}".lower()


def run_workflow_dispatch(project: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=project, check=False, text=True, capture_output=True)
    for _ in range(DEFAULT_GH_WORKFLOW_RUN_RETRIES):
        if not gh_transient_eof(result):
            break
        result = subprocess.run(command, cwd=project, check=False, text=True, capture_output=True)
    return result


def run_publish(args: argparse.Namespace) -> int:
    try:
        config = read_config(args.project)
        bump_plugins = parse_bump_plugins(args.bump_plugins)
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    if not args.authorize_publish:
        print("status: issues")
        print("error: publish_requires_authorize_publish")
        return 2

    result = run_workflow_dispatch(args.project, workflow_dispatch_args(config, args.tag, args.version, bump_plugins))
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def run_checked(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    resolved_command = list(command)
    if command and command[0] == "gh":
        gh_path = shutil.which("gh")
        if gh_path:
            resolved_command[0] = gh_path
    result = subprocess.run(
        resolved_command,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = " ".join(command)
        output = (result.stderr or result.stdout).strip()
        if output:
            detail = f"{detail}: {output}"
        raise ValueError(f"command_failed: {detail}")
    return result


def local_git_config_values(project: Path, key: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(project), "config", "--local", "--get-all", key],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise ValueError(f"command_failed: git config --local --get-all {key}")
    return result.stdout.splitlines()


def local_git_config_entries(project: Path) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "-C", str(project), "config", "--local", "--list"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError("command_failed: git config --local --list")
    entries: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if key and separator:
            entries.append((key, value))
    return entries


def add_local_git_config(project: Path, key: str, value: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(project), "config", "--local", "--add", key, value],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError(f"command_failed: git config --local --add {key}")


def copy_git_auth_config(source: Path, target: Path) -> None:
    for key, value in local_git_config_entries(source):
        if key.startswith("http.") and key.endswith(".extraheader"):
            add_local_git_config(target, key, value)
    for key in ["credential.helper", "credential.useHttpPath"]:
        for value in local_git_config_values(source, key):
            add_local_git_config(target, key, value)


def release_branch_name(tag: str) -> str:
    safe_tag = validate_release_tag(tag)
    return f"release-flow-{safe_tag}"


def workflow_run_url() -> str:
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""


def run_ci_publish_remote(
    project: Path, config: FlowConfig, projection: Projection, tag: str
) -> dict[str, str]:
    branch_name = release_branch_name(tag)
    with tempfile.TemporaryDirectory(prefix="release-flow-ci-") as temp_dir:
        release_tree = Path(temp_dir) / "release-tree"
        copy_project_for_expected(project, release_tree)
        apply_projection(release_tree, projection)
        run_checked(["git", "init"], release_tree)
        copy_git_auth_config(project, release_tree)
        run_checked(["git", "remote", "add", "origin", origin_url(project)], release_tree)
        run_checked(["git", "config", "user.name", "github-actions[bot]"], release_tree)
        run_checked(
            [
                "git",
                "config",
                "user.email",
                "41898282+github-actions[bot]@users.noreply.github.com",
            ],
            release_tree,
        )
        run_checked(["git", "checkout", "--orphan", branch_name], release_tree)
        run_checked(["git", "add", "-A"], release_tree)
        run_checked(["git", "commit", "-m", f"release: {tag}"], release_tree)
        marketplace_commit = git_output(release_tree, ["rev-parse", "HEAD"]).strip()
        run_checked(
            ["git", "push", "origin", f"HEAD:refs/heads/{config.release_channel_branch}", "--force"],
            release_tree,
        )
        run_checked(["git", "tag", "--", tag], release_tree)
        tag_commit = git_output(release_tree, ["rev-list", "-n", "1", tag]).strip()
        run_checked(["git", "push", "origin", f"refs/tags/{tag}"], release_tree)
        release = run_checked(
            ["gh", "release", "create", tag, "--title", tag, "--notes", f"Release {tag}"],
            release_tree,
        )
        return {
            "release_url": release.stdout.strip().splitlines()[0] if release.stdout.strip() else "",
            "marketplace_commit": marketplace_commit,
            "tag_commit": tag_commit,
            "workflow_run_url": workflow_run_url(),
        }


def run_ci_publish(args: argparse.Namespace) -> int:
    if not args.authorize_ci_publish:
        print("status: issues")
        print("error: ci_publish_requires_authorize_ci_publish")
        return 2

    try:
        config = read_config(args.project)
        projection = read_projection(args.project)
        errors = projection_errors(projection)
        if errors:
            raise ValueError(errors[0])
        bump_plugins = parse_bump_plugins(args.bump_plugins)
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    errors = preflight_errors(
        args.project,
        args.tag,
        args.version,
        bump_plugins,
        config,
        projection,
    )
    if errors:
        print("status: issues")
        print_preflight_errors(errors, args.project)
        return 1

    try:
        trace = run_ci_publish_remote(args.project, config, projection, args.tag)
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    print("status: ci_published")
    print(f"channel_branch: {config.release_channel_branch}")
    print(f"tag: {args.tag}")
    for key, value in trace.items():
        print(f"{key}: {value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Release Flow Plugin（发布流程插件）。")
    subparsers = parser.add_subparsers(dest="command", required=True)
    setup = subparsers.add_parser("setup", help="启用 release-flow 项目配置。")
    setup.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    setup.add_argument("--authorize-project-files", action="store_true", help="授权写入项目配置文件。")
    validate = subparsers.add_parser("validate", help="验证 release-flow 配置。")
    validate.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    project = subparsers.add_parser("project", help="应用 release-flow projection。")
    project.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    github_plan = subparsers.add_parser("github-plan", help="输出 GitHub release-flow 配置计划。")
    github_plan.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    configure_github = subparsers.add_parser("configure-github", help="输出或执行 GitHub release-flow 配置。")
    configure_github.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    configure_github.add_argument("--dry-run", action="store_true", help="只输出手动配置步骤。")
    configure_github.add_argument("--authorize-github", action="store_true", help="授权写入 GitHub 配置。")
    preflight = subparsers.add_parser("preflight", help="执行 release-flow 发布前检查。")
    preflight.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    preflight.add_argument("--tag", required=True, help="发布标签。")
    preflight.add_argument("--version", required=True, help="发布版本。")
    preflight.add_argument("--bump-plugins", action="append", required=True, help="逗号分隔插件名；空字符串表示不提升插件。")
    publish = subparsers.add_parser("publish", help="触发 GitHub release workflow。")
    publish.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    publish.add_argument("--tag", required=True, help="发布标签。")
    publish.add_argument("--version", required=True, help="发布版本。")
    publish.add_argument("--bump-plugins", action="append", required=True, help="逗号分隔插件名；空字符串表示不提升插件。")
    publish.add_argument("--authorize-publish", action="store_true", help="授权触发 GitHub 发布。")
    ci_publish = subparsers.add_parser("ci-publish", help="CI 中发布 release channel。")
    ci_publish.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    ci_publish.add_argument("--tag", required=True, help="发布标签。")
    ci_publish.add_argument("--version", required=True, help="发布版本。")
    ci_publish.add_argument("--bump-plugins", action="append", required=True, help="逗号分隔插件名；空字符串表示不提升插件。")
    ci_publish.add_argument("--authorize-ci-publish", action="store_true", help="授权 CI 远端写入。")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "setup":
        return run_setup(args)
    if args.command == "validate":
        return run_validate(args)
    if args.command == "project":
        return run_project(args)
    if args.command == "github-plan":
        return run_github_plan(args)
    if args.command == "configure-github":
        return run_configure_github(args)
    if args.command == "preflight":
        return run_preflight(args)
    if args.command == "publish":
        return run_publish(args)
    if args.command == "ci-publish":
        return run_ci_publish(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
