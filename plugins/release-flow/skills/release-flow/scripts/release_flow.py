"""Release Flow Plugin（发布流程插件）命令行入口。"""

from __future__ import annotations

import argparse
import zipfile
import uuid
import time
import threading
import queue
import hashlib
from dataclasses import dataclass
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlparse

try:
    import yaml
except ModuleNotFoundError as error:
    if error.name != "yaml":
        raise
    requirement = Path(__file__).resolve().parents[1] / "requirements.txt"
    raise SystemExit(f"missing_dependency: PyYAML（配置解析库）；当前解释器：{sys.executable}；"
                     f"依赖声明：{requirement}。未自动安装，请由用户决定补装。") from error


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"

FORBIDDEN_VARIABLE_VALUE_KEYS = {"value", "secret", "defaultValue", "default_value"}
SUPPORTED_VARIABLE_SOURCE = "github-actions-variable"
SUPPORTED_TRANSFORM_TYPE = "json-env"
SUPPORTED_GENERATOR_TYPE = "codex-marketplace"
SUPPORTED_GENERATOR_IDENTITY = "codex"
PLUGIN_REGISTRY: dict[str, dict[str, Any]] = {
    "dev-flow": {
        "releaseShape": "marketplace",
        "releaseInputs": [
            "plugins/dev-flow"
        ],
        "versionFiles": [
            "plugins/dev-flow/.codex-plugin/plugin.json",
            "plugins/dev-flow/.claude-plugin/plugin.json"
        ],
        "codexMarketplace": {
            "name": "dev-flow",
            "source": {
                "source": "local",
                "path": "./plugins/dev-flow"
            },
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL"
            },
            "category": "Developer Tools"
        }
    },
    "subagent-policy": {
        "releaseShape": "marketplace",
        "releaseInputs": [
            "plugins/subagent-policy"
        ],
        "versionFiles": [
            "plugins/subagent-policy/.codex-plugin/plugin.json",
            "plugins/subagent-policy/.claude-plugin/plugin.json"
        ],
        "codexMarketplace": {
            "name": "subagent-policy",
            "source": {
                "source": "local",
                "path": "./plugins/subagent-policy"
            },
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL"
            },
            "category": "Developer Tools"
        }
    },
    "plugin-sync": {
        "releaseShape": "marketplace",
        "releaseInputs": [
            "plugins/plugin-sync"
        ],
        "versionFiles": [
            "plugins/plugin-sync/.codex-plugin/plugin.json",
            "plugins/plugin-sync/.claude-plugin/plugin.json"
        ],
        "codexMarketplace": {
            "name": "plugin-sync",
            "source": {
                "source": "local",
                "path": "./plugins/plugin-sync"
            },
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL"
            },
            "category": "Developer Tools"
        }
    },
    "retro-to-issues": {
        "releaseShape": "marketplace",
        "releaseInputs": [
            "plugins/retro-to-issues"
        ],
        "versionFiles": [
            "plugins/retro-to-issues/.codex-plugin/plugin.json",
            "plugins/retro-to-issues/.claude-plugin/plugin.json"
        ],
        "codexMarketplace": {
            "name": "retro-to-issues",
            "source": {
                "source": "local",
                "path": "./plugins/retro-to-issues"
            },
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL"
            },
            "category": "Developer Tools"
        }
    },
    "data-store": {
        "releaseShape": "marketplace",
        "releaseInputs": ["plugins/data-store"],
        "versionFiles": [
            "plugins/data-store/.codex-plugin/plugin.json",
            "plugins/data-store/.claude-plugin/plugin.json",
        ],
        "codexMarketplace": {
            "name": "data-store",
            "source": {"source": "local", "path": "./plugins/data-store"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
    "release-flow": {
        "releaseShape": "marketplace",
        "releaseInputs": ["plugins/release-flow"],
        "versionFiles": [
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
    "pr-flow": {
        "releaseShape": "marketplace",
        "releaseInputs": ["plugins/pr-flow"],
        "versionFiles": [
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
        "releaseShape": "npm",
        "commandTool": {"package": "@liuli195/build-and-verify", "command": "build-and-verify"},
        "releaseInputs": [
            "plugins/build-and-verify",
            "plugins/tool-lifecycle/python/management.py",
            "plugins/tool-lifecycle/pack.py",
        ],
        "versionFiles": [
            "plugins/build-and-verify/.codex-plugin/plugin.json",
            "plugins/build-and-verify/.claude-plugin/plugin.json",
            "plugins/build-and-verify/package.json",
        ],
        "codexMarketplace": {
            "name": "build-and-verify",
            "source": {"source": "local", "path": "./plugins/build-and-verify"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
    "my-spec": {
        "releaseShape": "npm",
        "commandTool": {"package": "@liuli195/myspec", "command": "myspec"},
        "releaseInputs": [
            "plugins/my-spec",
            "plugins/tool-lifecycle/python/management.py",
            "plugins/tool-lifecycle/pack.py",
        ],
        "versionFiles": [
            "plugins/my-spec/.codex-plugin/plugin.json",
            "plugins/my-spec/.claude-plugin/plugin.json",
            "plugins/my-spec/package.json",
        ],
        "codexMarketplace": {
            "name": "my-spec",
            "source": {"source": "local", "path": "./plugins/my-spec"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    },
}
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
    errors = projection_errors(projection)
    if errors:
        return errors
    return npm_repository_metadata_errors(project)


def print_project_errors(errors: list[str], command: str) -> None:
    for error in errors:
        print(f"error: {error}")
        next_action = release_metadata_next_action(error, command)
        if next_action:
            print(f"nextAction: {next_action}")


def run_validate(args: argparse.Namespace) -> int:
    errors = validate_project(args.project)
    if errors:
        print("status: issues")
        print_project_errors(errors, "validate")
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
        print_project_errors(errors, "project")
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


def semver_key(version: str) -> tuple[tuple[int, int, int], tuple[tuple[int, int | str], ...]] | None:
    main, has_build, build = version.partition("+")
    if has_build and (
        not build
        or any(
            not identifier
            or any(not character.isascii() or not (character.isalnum() or character == "-") for character in identifier)
            for identifier in build.split(".")
        )
    ):
        return None
    core, has_prerelease, prerelease = main.partition("-")
    parts = core.split(".")
    if len(parts) != 3 or any(
        not part
        or any(not character.isascii() or not character.isdigit() for character in part)
        or (len(part) > 1 and part.startswith("0"))
        for part in parts
    ):
        return None
    prerelease_key: list[tuple[int, int | str]] = []
    if has_prerelease:
        for identifier in prerelease.split("."):
            if not identifier or any(
                not character.isascii() or not (character.isalnum() or character == "-")
                for character in identifier
            ):
                return None
            if identifier.isdigit():
                if len(identifier) > 1 and identifier.startswith("0"):
                    return None
                prerelease_key.append((0, int(identifier)))
            else:
                prerelease_key.append((1, identifier))
    return (tuple(int(part) for part in parts), tuple(prerelease_key))


def version_is_advanced(current: str, baseline: str) -> bool:
    current_key = semver_key(current)
    baseline_key = semver_key(baseline)
    if current_key is None or baseline_key is None:
        return False
    current_core, current_prerelease = current_key
    baseline_core, baseline_prerelease = baseline_key
    if current_core != baseline_core:
        return current_core > baseline_core
    if not current_prerelease or not baseline_prerelease:
        return not current_prerelease and bool(baseline_prerelease)
    for current_identifier, baseline_identifier in zip(current_prerelease, baseline_prerelease):
        if current_identifier != baseline_identifier:
            if current_identifier[0] != baseline_identifier[0]:
                return current_identifier[0] > baseline_identifier[0]
            return current_identifier[1] > baseline_identifier[1]
    return len(current_prerelease) > len(baseline_prerelease)


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


def plugin_release_inputs(plugin_name: str) -> list[str]:
    try:
        inputs = PLUGIN_REGISTRY[plugin_name]["releaseInputs"]
    except KeyError as exc:
        raise ValueError(f"plugin_unknown: {plugin_name}") from exc
    if not isinstance(inputs, list) or not all(isinstance(path, str) for path in inputs):
        raise ValueError(f"plugin_release_inputs_invalid: {plugin_name}")
    return list(inputs)


def plugin_version_files(plugin_name: str) -> list[str]:
    try:
        version_files = PLUGIN_REGISTRY[plugin_name]["versionFiles"]
    except KeyError as exc:
        raise ValueError(f"plugin_unknown: {plugin_name}") from exc
    if not isinstance(version_files, list) or not all(isinstance(path, str) for path in version_files):
        raise ValueError(f"plugin_version_files_invalid: {plugin_name}")
    return list(version_files)


def plugin_release_shape(plugin_name: str) -> str:
    try:
        shape = PLUGIN_REGISTRY[plugin_name]["releaseShape"]
    except KeyError as exc:
        raise ValueError(f"plugin_unknown: {plugin_name}") from exc
    if shape not in {"marketplace", "npm"}:
        raise ValueError(f"plugin_release_shape_invalid: {plugin_name}")
    return str(shape)


def github_repository_identity_from_url(value: str) -> str | None:
    if not value or value != value.strip():
        return None
    path: str
    if value.lower().startswith("git@"):
        prefix, separator, path = value.partition(":")
        if not separator or prefix.lower() != "git@github.com":
            return None
    else:
        try:
            parsed = urlparse(value)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            return None
        if parsed.scheme not in {"https", "git+https", "ssh", "git+ssh"}:
            return None
        if hostname != "github.com" or port is not None or parsed.password:
            return None
        if parsed.query or parsed.fragment:
            return None
        if parsed.scheme in {"https", "git+https"} and parsed.username is not None:
            return None
        if parsed.scheme in {"ssh", "git+ssh"} and parsed.username not in {None, "git"}:
            return None
        path = parsed.path

    parts = path.strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        return None
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not repository:
        return None
    return f"{owner}/{repository}"


def github_repository_identity_from_environment(value: str) -> str | None:
    if not value or value != value.strip():
        return None
    parts = value.split("/")
    if len(parts) != 2 or not all(parts) or any(part in {".", ".."} for part in parts):
        return None
    return value


def github_repository_identity(project: Path) -> str:
    origin_value = origin_url(project)
    origin_identity = github_repository_identity_from_url(origin_value)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        environment_value = os.environ.get("GITHUB_REPOSITORY", "")
        environment_identity = github_repository_identity_from_environment(environment_value)
        if environment_identity is None:
            actual = environment_value or "<missing>"
            raise ValueError(
                "npm_repository_identity_unavailable: GITHUB_REPOSITORY "
                f"expected=owner/repository actual={actual}"
            )
        if origin_identity and environment_identity != origin_identity:
            raise ValueError(
                "npm_repository_identity_conflict: repository identity "
                f"expected={environment_identity} actual={origin_identity}"
            )
        return environment_identity

    if origin_identity:
        return origin_identity
    actual = origin_value or "<missing>"
    raise ValueError(
        "npm_repository_identity_unavailable: origin "
        f"expected=GitHub owner/repository actual={actual}"
    )


def npm_repository_metadata_errors(
    project: Path, plugin_names: Iterable[str] | None = None
) -> list[str]:
    selected = set(plugin_names) if plugin_names is not None else None
    manifests: list[tuple[str, Path, Path]] = []
    errors: list[str] = []
    for plugin_name in sorted(PLUGIN_REGISTRY):
        if selected is not None and plugin_name not in selected:
            continue
        if plugin_release_shape(plugin_name) != "npm":
            continue
        release_inputs = plugin_release_inputs(plugin_name)
        package_directory = Path(release_inputs[0])
        manifest_relative = package_directory / "package.json"
        try:
            manifest_path = resolve_project_path(project, manifest_relative, "invalid_manifest_path")
        except ValueError as exc:
            errors.append(
                "npm_package_manifest_invalid: "
                f"{manifest_relative.as_posix()} expected=inside-project actual={exc}"
            )
            continue
        if not manifest_path.is_file():
            if selected is not None or (project / package_directory).exists():
                errors.append(
                    "npm_package_manifest_missing: "
                    f"{manifest_relative.as_posix()} expected=package.json actual=<missing>"
                )
            continue
        manifests.append((plugin_name, package_directory, manifest_path))

    if not manifests:
        return errors
    try:
        expected_repository = github_repository_identity(project)
    except ValueError as exc:
        prefix, detail = str(exc).split(": ", 1)
        errors.extend(
            f"{prefix}: {manifest_path.relative_to(project.resolve()).as_posix()} {detail}"
            for _plugin_name, _package_directory, manifest_path in manifests
        )
        return errors

    for _plugin_name, package_directory, manifest_path in manifests:
        manifest_label = manifest_path.relative_to(project.resolve()).as_posix()
        try:
            package = read_json_mapping(manifest_path)
        except ValueError as exc:
            errors.append(
                "npm_package_manifest_invalid: "
                f"{manifest_label} expected=valid JSON actual={exc}"
            )
            continue

        repository = package.get("repository")
        if isinstance(repository, str):
            repository_url: Any = repository
            repository_directory: Any = None
        elif isinstance(repository, dict):
            repository_url = repository.get("url")
            repository_directory = repository.get("directory")
        else:
            repository_url = None
            repository_directory = None

        if not isinstance(repository_url, str) or not repository_url:
            errors.append(
                "npm_repository_url_missing: "
                f"{manifest_label} expected={expected_repository} actual=<missing>"
            )
        else:
            actual_repository = github_repository_identity_from_url(repository_url)
            if actual_repository is None:
                errors.append(
                    "npm_repository_url_invalid: "
                    f"{manifest_label} expected={expected_repository} actual={repository_url}"
                )
            elif actual_repository != expected_repository:
                errors.append(
                    "npm_repository_url_mismatch: "
                    f"{manifest_label} expected={expected_repository} actual={actual_repository}"
                )

        expected_directory = package_directory.as_posix()
        if not isinstance(repository_directory, str) or not repository_directory:
            errors.append(
                "npm_repository_directory_missing: "
                f"{manifest_label} expected={expected_directory} actual=<missing>"
            )
        elif repository_directory != expected_directory:
            errors.append(
                "npm_repository_directory_mismatch: "
                f"{manifest_label} expected={expected_directory} actual={repository_directory}"
            )
    return errors


def release_metadata_next_action(error: str, command: str) -> str:
    if error.startswith("npm_repository_identity_unavailable:"):
        return (
            "configure a GitHub origin or trusted GITHUB_REPOSITORY, then rerun "
            f"release-flow {command}"
        )
    if error.startswith("npm_repository_identity_conflict:"):
        return (
            "align the GitHub origin and GITHUB_REPOSITORY identity, then rerun "
            f"release-flow {command}"
        )
    if error.startswith(("npm_",)):
        detail = error.split(": ", 1)[1] if ": " in error else ""
        manifest = detail.split(" ", 1)[0] if detail else "the package manifest"
        return f"correct npm repository metadata in {manifest}, then rerun release-flow {command}"
    return ""


def manifest_version(project: Path, manifest_file: str) -> str:
    manifest_path = resolve_project_path(project, Path(manifest_file), "invalid_manifest_path")
    manifest = read_json_mapping(manifest_path)
    version = manifest.get("version")
    if not isinstance(version, str):
        raise ValueError(f"manifest_version_missing: {manifest_file}")
    return version


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


def ensure_remote_branch(project: Path, branch: str, *, refresh: bool = False) -> None:
    ref = f"origin/{branch}"
    if not refresh and git_ref_exists(project, ref):
        return
    result = subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "fetch",
            "--depth=1",
            "origin",
            f"+{branch}:refs/remotes/origin/{branch}",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise ValueError(f"remote_ref_missing: {ref}: {output}")


def git_path_exists(project: Path, ref: str, path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(project), "ls-tree", "--name-only", ref, "--", path.as_posix()],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise ValueError(f"command_failed: git ls-tree {ref}: {output}")
    return bool(result.stdout.strip())


def plugin_target_exists(project: Path, config: FlowConfig, plugin_name: str) -> bool:
    release_inputs = plugin_release_inputs(plugin_name)
    root = Path(release_inputs[0])
    if (project / root).exists():
        return True
    ensure_remote_branch(project, config.release_channel_branch)
    return git_path_exists(project, f"origin/{config.release_channel_branch}", root)


def git_paths_changed(project: Path, revisions: list[str], paths: list[str]) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "diff",
            "--quiet",
            *revisions,
            "--",
            *(Path(path).as_posix() for path in paths),
        ],
        check=False,
        capture_output=True,
    )
    if result.returncode not in {0, 1}:
        output = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"command_failed: git diff {' '.join(revisions)}: {output}")
    return result.returncode == 1


def release_input_changed(project: Path, config: FlowConfig, plugin_name: str) -> bool:
    release_inputs = plugin_release_inputs(plugin_name)
    for release_input in release_inputs:
        resolve_project_path(project, Path(release_input), "invalid_release_input_path")
    ensure_remote_branch(project, config.release_channel_branch)
    ensure_remote_branch(project, config.release_source_ref)
    channel_ref = f"origin/{config.release_channel_branch}"
    source_ref = f"origin/{config.release_source_ref}"
    if git_paths_changed(project, [channel_ref], release_inputs):
        return True
    if git_paths_changed(project, [source_ref], release_inputs):
        return True
    return source_ref != channel_ref and git_paths_changed(
        project,
        [source_ref, channel_ref],
        release_inputs,
    )


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
    tag_exists = bool(tag_result.stdout.strip())
    if not tag_exists:
        return errors
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
        if tag_exists:
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
    metadata_errors = npm_repository_metadata_errors(project, bump_plugins)
    if metadata_errors:
        errors.extend(metadata_errors)
        return errors

    try:
        for branch in dict.fromkeys((config.release_channel_branch, config.release_source_ref)):
            ensure_remote_branch(project, branch, refresh=True)
    except ValueError as exc:
        errors.append(str(exc))
        errors.extend(remote_release_errors(project, tag))
        return errors

    projection_plugins = sorted({plugin for generator in projection.generators for plugin in generator.plugins})
    for plugin_name in projection_plugins:
        if plugin_name not in PLUGIN_REGISTRY:
            errors.append(f"projection_generator_plugin_unknown: {plugin_name}")

    published_plugins = set(projection_plugins)
    published_plugins.update(
        plugin_name
        for plugin_name in PLUGIN_REGISTRY
        if plugin_release_shape(plugin_name) == "npm"
        or plugin_target_exists(project, config, plugin_name)
    )
    bumped = set(bump_plugins)
    for plugin_name in sorted(published_plugins):
        if plugin_name not in PLUGIN_REGISTRY:
            continue
        if (
            plugin_name not in projection_plugins
            and plugin_release_shape(plugin_name) == "npm"
            and not plugin_target_exists(project, config, plugin_name)
        ):
            continue
        try:
            input_changed = release_input_changed(project, config, plugin_name)
            version_files = plugin_version_files(plugin_name)
            current_versions = {
                version_file: manifest_version(project, version_file)
                for version_file in version_files
            }
            baseline_versions = {
                version_file: remote_ref_manifest_version(
                    project,
                    config.release_channel_branch,
                    version_file,
                )
                for version_file in version_files
            }
            if plugin_name in bumped:
                for version_file, current in current_versions.items():
                    if current != version:
                        errors.append(f"manifest_version_mismatch: {version_file}")
                    source = source_ref_manifest_version(project, config, version_file)
                    if source != version:
                        errors.append(
                            f"source_ref_requires_pr: {config.release_source_ref}: {version_file}"
                        )
                if input_changed and any(
                    baseline is not None
                    and not version_is_advanced(current_versions[version_file], baseline)
                    for version_file, baseline in baseline_versions.items()
                ):
                    errors.append(f"plugin_version_not_bumped: {plugin_name}")
            elif input_changed:
                errors.append(f"plugin_requires_bump: {plugin_name}")
            elif any(
                baseline is None or current_versions[version_file] != baseline
                for version_file, baseline in baseline_versions.items()
            ):
                errors.append(f"plugin_requires_bump: {plugin_name}")
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(str(exc))

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
    metadata_action = release_metadata_next_action(error, "preflight")
    if metadata_action:
        return metadata_action
    if error.startswith("source_ref_requires_pr: "):
        return "create and merge the version bump through PR Flow, then rerun release-flow preflight"
    if error.startswith("plugin_version_not_bumped: "):
        return "advance the plugin version through PR Flow, then rerun release-flow preflight"
    if error.startswith("manifest_version_mismatch: "):
        manifest_path = error.split(": ", 1)[1]
        return f"correct the manifest version in {manifest_path}, then rerun release-flow preflight"
    if error.startswith("release already exists: "):
        return (
            "requested release/tag already exists; choose the release version with the user and agent, "
            "then rerun release-flow preflight"
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
        "plugin_version_not_bumped: ",
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
    if any(error.startswith("plugin_version_not_bumped: ") for error in errors):
        states.append("selected plugins need a version advancement")
        actions.append("advance selected plugin versions through PR Flow")
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


def without_existing_release_error(errors: list[str], tag: str) -> list[str]:
    existing = f"release already exists: {tag}"
    return [error for error in errors if error != existing]


def remote_ref_oid(project: Path, kind: str, ref: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(project), "ls-remote", f"--{kind}", "origin", ref],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.stdout.split()[0] if result.returncode == 0 and result.stdout.strip() else ""


def existing_release_ref_error(
    project: Path, config: FlowConfig, projection: Projection, tag: str
) -> str | None:
    tag_commit = remote_ref_oid(project, "tags", f"refs/tags/{tag}")
    channel_commit = remote_ref_oid(
        project, "heads", f"refs/heads/{config.release_channel_branch}"
    )
    if not tag_commit or not channel_commit:
        return f"remote_release_unknown: {tag}"
    if tag_commit != channel_commit:
        return f"release_tag_channel_mismatch: {tag}"

    with tempfile.TemporaryDirectory(prefix="release-flow-verify-") as temp_dir:
        temp_root = Path(temp_dir)
        expected = temp_root / "expected"
        copy_project_for_expected(project, expected)
        apply_projection(expected, projection)
        run_checked(["git", "init"], expected)
        run_checked(["git", "add", "-A"], expected)
        expected_tree = git_output(expected, ["write-tree"]).strip()

        remote = temp_root / "remote"
        remote.mkdir()
        run_checked(["git", "init"], remote)
        copy_git_auth_config(project, remote)
        run_checked(["git", "remote", "add", "origin", origin_url(project)], remote)
        run_checked(["git", "fetch", "--depth=1", "origin", tag_commit], remote)
        remote_tree = git_output(remote, ["rev-parse", "FETCH_HEAD^{tree}"]).strip()
    if remote_tree != expected_tree:
        return f"release_projection_mismatch: {tag}"
    return None


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
        if args.allow_existing_release:
            had_existing_release = len(errors) != len(
                without_existing_release_error(errors, args.tag)
            )
            errors = without_existing_release_error(errors, args.tag)
            if had_existing_release:
                ref_error = existing_release_ref_error(
                    args.project, config, projection, args.tag
                )
                if ref_error:
                    errors.append(ref_error)
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

    metadata_errors = npm_repository_metadata_errors(args.project, bump_plugins)
    if metadata_errors:
        print("status: issues")
        print_project_errors(metadata_errors, "publish")
        return 1

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


def recover_existing_ci_publish(
    project: Path, config: FlowConfig, projection: Projection, tag: str
) -> dict[str, str]:
    ref_error = existing_release_ref_error(project, config, projection, tag)
    if ref_error:
        raise ValueError(ref_error)
    tag_commit = remote_ref_oid(project, "tags", f"refs/tags/{tag}")
    marketplace_commit = remote_ref_oid(
        project, "heads", f"refs/heads/{config.release_channel_branch}"
    )

    release_view = subprocess.run(
        ["gh", "release", "view", tag, "--json", "url", "--jq", ".url"],
        cwd=project,
        check=False,
        text=True,
        capture_output=True,
    )
    release_output = (release_view.stderr or release_view.stdout).lower()
    if release_view.returncode == 0:
        release_url = release_view.stdout.strip()
    elif "not found" in release_output or "could not resolve" in release_output:
        release = run_checked(
            ["gh", "release", "create", tag, "--title", tag, "--notes", f"Release {tag}"],
            project,
        )
        release_url = release.stdout.strip().splitlines()[0] if release.stdout.strip() else ""
    else:
        raise ValueError(f"remote_release_unknown: {tag}")

    return {
        "release_url": release_url,
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
    existing_release_error = f"release already exists: {args.tag}"
    recover_existing = bool(errors) and all(error == existing_release_error for error in errors)
    if errors and not recover_existing:
        print("status: issues")
        print_preflight_errors(errors, args.project)
        return 1

    try:
        trace = (
            recover_existing_ci_publish(args.project, config, projection, args.tag)
            if recover_existing
            else run_ci_publish_remote(args.project, config, projection, args.tag)
        )
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



class SwitchError(Exception):
    pass


def remaining_timeout(limit: float, deadline: float) -> float:
    remaining = min(limit, deadline - time.monotonic())
    if remaining <= 0:
        raise SwitchError("operation budget exhausted; no further client writes are allowed")
    return remaining


def unresolved_account_save(manifest: dict) -> dict | None:
    for mapping in manifest["plugins"].values():
        for source in mapping.get("account", {}).values():
            state = source.get("saveState", {})
            if state.get("status") not in (None, "verified"):
                return state
    return None


class AppServer:
    """One owned stdio process for account preflight, save and readback."""

    def __init__(self, command: list[str], cwd: str, timeout: float, deadline: float):
        self.timeout = timeout
        self.deadline = deadline
        self.sequence = 0
        self.pending_writes: dict[int, dict] = {}
        self.messages: queue.Queue = queue.Queue()
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=None,
                                        text=True, encoding="utf-8", bufsize=1)
        def read() -> None:
            try:
                for line in self.process.stdout:
                    self.messages.put(json.loads(line))
            except (ValueError, OSError) as error:
                self.messages.put(error)
            finally:
                self.messages.put(None)
        threading.Thread(target=read, daemon=True).start()

    def notify(self, method: str, params: dict | None = None) -> None:
        value = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            value["params"] = params
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def call(self, method: str, params: dict, timeout: float | None = None) -> dict:
        deadline = time.monotonic() + remaining_timeout(min(self.timeout, timeout or self.timeout), self.deadline)
        mutating = method == "plugin/share/save"
        if mutating and self.pending_writes:
            raise SwitchError("unresolved account write; no further writes or compensation are allowed")
        self.sequence += 1
        request_id = self.sequence
        if mutating:
            self.pending_writes[request_id] = {"requestId": request_id, "method": method, "params": params}
        self.process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id,
                                             "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        while True:
            try:
                value = self.messages.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty as error:
                raise SwitchError(f"app-server timeout: {method}; " +
                                  ("write outcome unresolved; compensation stopped" if mutating else "response unavailable")) from error
            if value is None or isinstance(value, Exception):
                raise SwitchError(f"app-server unavailable: {method}; outcome unknown")
            if "method" in value and "id" in value:
                raise SwitchError("unexpected server request; no authentication or approval was accepted")
            if isinstance(value.get("result"), dict) or "error" in value:
                self.pending_writes.pop(value.get("id"), None)
            if value.get("id") != request_id:
                continue
            if "error" in value:
                raise SwitchError(f"{method}: {value['error']}")
            if not isinstance(value.get("result"), dict):
                raise SwitchError(f"invalid app-server result: {method}")
            return value["result"]

    def close(self) -> None:
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)


def verified_snapshot(path: str, plugin: str, expected: str, mode: str, deadline: float) -> dict:
    """Validate the existing pack.py manifest and exact directory without rebuilding."""
    if not path or not expected or len(expected) != 64:
        raise SwitchError("save-account requires --snapshots and the reviewed --expected-sha256")
    manifest_path = Path(path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        raise SwitchError("unsupported snapshot manifest version")
    snapshot = manifest["plugins"][plugin]
    package_name = snapshot.get("packageName")
    if mode != "RELEASE" or snapshot.get("accountMode") != "RELEASE" or package_name != plugin:
        raise SwitchError("save-account requires an explicitly packaged matching account mode and packageName")
    hashes = ((snapshot["sha256"], 64), (snapshot["inputVersion"], 64), (snapshot["sourceCommit"], 40))
    if (snapshot["sha256"] != expected or any(not isinstance(value, str) or len(value) != size
            or any(character not in "0123456789abcdef" for character in value) for value, size in hashes)
            or not isinstance(snapshot["sourceDirty"], bool)
            or not snapshot.get("metadataSource", {}).get("repository")):
        raise SwitchError("snapshot digest or recorded source provenance is not verified")
    if snapshot["sourceDirty"]:
        raise SwitchError("a dirty development snapshot cannot overwrite a RELEASE object")
    release_ref = snapshot.get("releaseRef")
    if not isinstance(release_ref, str) or not release_ref.startswith("refs/tags/") or not release_ref.removeprefix("refs/tags/"):
        raise SwitchError("RELEASE snapshots require the reviewed existing release tag reference")
    root = manifest_path.parent
    artifact = root / snapshot["artifact"]
    recorded_path = snapshot.get("pluginPath")
    if (not isinstance(recorded_path, str) or ".." in recorded_path.replace("\\", "/").split("/")
            or recorded_path.replace("\\", "/").rsplit("/", 1)[-1] != artifact.stem):
        raise SwitchError("snapshot pluginPath is not the recorded archive directory")
    # CI paths are machine-local. Only the verified sibling directory is transmitted.
    directory = root / artifact.stem
    if (artifact.parent != root or artifact.suffix != ".zip" or artifact.is_symlink() or not artifact.is_file()
            or directory.is_symlink() or not directory.is_dir()
            or artifact.stat().st_size != snapshot["sizeBytes"]):
        raise SwitchError("snapshot archive or pluginPath is not a verified sibling artifact")
    snapshot = {**snapshot, "pluginPath": str(directory)}
    # Bound compressed and expanded input together below the user's disk budget.
    with zipfile.ZipFile(artifact) as archive:
        if artifact.stat().st_size + sum(item.file_size for item in archive.infolist()) > 500_000_000:
            raise SwitchError("snapshot exceeds the bounded save budget; request user approval")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
            raise SwitchError("snapshot archive digest mismatch")
        entries = archive.namelist()
        paths = list(directory.rglob("*"))
        files = {item.relative_to(directory).as_posix(): item for item in paths if item.is_file()}
        if (len(entries) != len(set(entries)) or set(files) != set(entries)
                or any(item.is_symlink() for item in paths)):
            raise SwitchError("snapshot directory does not match the complete archive")
        for name, item in files.items():
            remaining_timeout(120, deadline)
            if (item.stat().st_size != archive.getinfo(name).file_size
                    or item.read_bytes() != archive.read(name)
                    or (os.name != "nt" and archive.getinfo(name).create_system == 3
                        and (item.stat().st_mode & 0o111) != ((archive.getinfo(name).external_attr >> 16) & 0o111))):
                raise SwitchError("snapshot directory content or executable mode mismatch")
    metadata = json.loads((directory / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    if metadata.get("name") != package_name or metadata.get("version") != snapshot["version"]:
        raise SwitchError("snapshot plugin identity or version mismatch")
    return snapshot


def account_inventory(server: AppServer, timeout: float | None = None) -> list[dict]:
    response = server.call("plugin/list", {"marketplaceKinds": ["created-by-me-remote"], "forceRefetch": True}, timeout=timeout)
    if response.get("marketplaceLoadErrors"):
        raise SwitchError("account inventory is incomplete; marketplace loading failed")
    return [item for market in response["marketplaces"] for item in market["plugins"]]


def account_object(catalog: list[dict], remote_id: str, plugin: str, version: str) -> dict:
    found = [item for item in catalog if item.get("remotePluginId") == remote_id]
    if len(found) != 1:
        raise SwitchError("expected exactly one owned account object in the personal marketplace")
    discovered = found[0]
    if discovered.get("name") != plugin or discovered.get("version") != version:
        raise SwitchError("account object identity or version does not match the explicit mapping")
    identity = discovered.get("id")
    if not isinstance(identity, str) or not identity or any(
            value.get("id") == identity and value.get("remotePluginId") != remote_id for value in catalog):
        raise SwitchError("account discovery identity is missing or conflicts; no rename was attempted")
    # USER plugins intentionally have no shareContext. The workspace-only share/list
    # cannot verify their permissions and is not a prerequisite for request completion.
    context = discovered.get("shareContext")
    scope = discovered.get("scope")
    if scope not in (None, "USER"):
        raise SwitchError("account scope is not personal USER; workspace objects are not supported")
    if discovered.get("discoverability") not in (None, "PRIVATE"):
        raise SwitchError("account object has explicitly non-private discoverability")
    if context is not None:
        raise SwitchError("workspace sharing metadata conflicts with the personal account path; sharing was not changed")
    permissions = {"status": "not_available", "evidence": "personal marketplace; no shareContext",
                   "scope": scope, "creatorApiQueried": False}
    return {key: discovered.get(key) for key in
            ("id", "remotePluginId", "name", "version", "installed", "enabled", "localVersion")} | {"permissions": permissions}


def write_mapping(path: Path, manifest: dict, original: bytes) -> bytes:
    if path.read_bytes() != original:
        raise SwitchError("mapping changed concurrently; no further writes are allowed")
    payload = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".release-account-", delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
        return payload
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def reconcile_state(source: dict) -> dict:
    state = source.get("saveState", {})
    remote_id = state.get("responseRemotePluginId")
    snapshot = state.get("snapshot", {})
    if (state.get("status") != "unverified" or state.get("operation") not in ("create", "update")
            or not isinstance(remote_id, str) or not remote_id or source.get("remotePluginId") != remote_id
            or state.get("responseSchemaVerified") is False
            or not source.get("packageName") or source.get("packageName") != snapshot.get("packageName")
            or not source.get("version") or source.get("version") != snapshot.get("version")):
        raise SwitchError("reconciliation requires an unverified successful save response with its exact recorded ID, package and version; pending or unknown writes remain blocked")
    return state


def save_account(args: argparse.Namespace) -> int:
    """One private object per invocation, with a durable no-retry marker before saving."""
    report = {"plugin": args.plugin, "target": args.mode, "action": args.action, "status": "blocked"}
    args.delivery_report = report
    server = None
    deadline = args.deadline
    try:
        if args.action == "save-account" and args.mode != "RELEASE":
            raise SwitchError("cloud DEV saves are retired; use the existing local development marketplace")
        if not 0 < args.timeout <= 120 or not 0 < args.ready_timeout <= 300 or not 0 < args.poll_interval <= 10:
            raise SwitchError("timeouts must be positive and bounded (request <=120s, readiness <=300s, poll <=10s)")
        path = Path(args.manifest).resolve()
        original = path.read_bytes()
        manifest = json.loads(original)
        mapping = manifest["plugins"][args.plugin]
        sources = mapping["account"]
        source = sources[args.mode]
        reconciling = args.action == "reconcile-account"
        if reconciling:
            report["saveState"] = source.get("saveState", {})
            state = reconcile_state(source)
            snapshot = state["snapshot"]
            package_name = source["packageName"]
            remote_id = state["responseRemotePluginId"]
        else:
            # Stop expansion as well as retries after an unresolved or unverified save.
            pending = unresolved_account_save(manifest)
            if pending:
                report["saveState"] = pending
                raise SwitchError("previous account save is unresolved or unverified; inspect native state before any retry")
            snapshot = verified_snapshot(args.snapshots, args.plugin, args.expected_sha256, args.mode, deadline)
            package_name = snapshot["packageName"]
            if source.get("packageName", package_name) != package_name:
                raise SwitchError("snapshot packageName differs from the authorized account mapping; no rename was attempted")
            remote_id = source.get("remotePluginId")
            if remote_id is not None and (not isinstance(remote_id, str) or not remote_id):
                raise SwitchError("remotePluginId must be a verified nonempty string or absent for first creation")
            report["release"] = published_account_release(args.project, snapshot, deadline)
            report["publicationStatus"] = "published"
        if remote_id and any(value.get("remotePluginId") == remote_id for mode, value in sources.items() if mode != args.mode):
            raise SwitchError("DEV and RELEASE cannot share an account object")
        server = AppServer(manifest.get("codexCommand", ["codex", "app-server", "--stdio"]),
                           args.cwd, args.timeout, deadline)
        server.call("initialize", {"clientInfo": {"name": "release-flow", "version": "1"},
                                   "capabilities": {"experimentalApi": True}})
        server.notify("initialized")
        catalog = account_inventory(server)
        if reconciling:
            report["after"] = account_object(catalog, remote_id, package_name, source["version"])
            report["privateCreationRequest"] = state.get("privateCreationRequest", {"status": "not_recorded"})
            report["status"] = "checked"
            if args.apply:
                state.update(status="verified", reconciled=True, permissions=report["after"]["permissions"],
                             privateCreationRequest=report["privateCreationRequest"])
                original = write_mapping(path, manifest, original)
                report["status"] = "reconciled"
            report["accountWrites"] = 0
            return 0
        if remote_id:
            report["before"] = account_object(catalog, remote_id, package_name, source["version"])
            previous = source.get("saveState", {})
            if (previous.get("status") != "verified" or previous.get("operation") not in ("create", "update")
                    or previous.get("responseRemotePluginId") != remote_id or previous.get("responseSchemaVerified") is False
                    or previous.get("privateCreationRequest") != {"discoverability": "PRIVATE", "shareTargets": []}
                    or previous.get("snapshot", {}).get("packageName") != package_name
                    or previous.get("snapshot", {}).get("version") != source["version"]):
                raise SwitchError("update requires this object's verified private creation record; unknown provenance remains blocked")
        elif any(item.get("name") == package_name for item in catalog):
            raise SwitchError("an account object with this package name already exists; verify and map its real ID before creation")
        report["operation"] = "update" if remote_id else "create"
        report["snapshot"] = {key: snapshot[key] for key in
                              ("sha256", "version", "sourceCommit", "sourceDirty", "inputVersion", "metadataSource", "accountMode", "packageName", "releaseRef")}
        if not args.apply:
            report["status"] = "checked"
            report["next"] = "review source contents and authorize this exact private save before --apply"
            return 0

        state = {"status": "pending", "operationId": str(uuid.uuid4()), "operation": report["operation"],
                 "remotePluginId": remote_id, "snapshot": report["snapshot"]}
        if getattr(args, "delivery_directory", None):
            state["deliveryDirectory"] = str(args.delivery_directory)
        # Preserve actual creation request evidence, not a claim about the object's current audience.
        state["privateCreationRequest"] = previous["privateCreationRequest"] if remote_id else {"discoverability": "PRIVATE", "shareTargets": []}
        source["saveState"] = state
        original = write_mapping(path, manifest, original)  # A crash after this point blocks repeats even across invocations.
        report["saveState"] = state
        print(json.dumps({"event": "before_account_save", **report}, ensure_ascii=False), flush=True)
        # Recheck the reviewed artifact immediately before transmitting any bytes.
        if verified_snapshot(args.snapshots, args.plugin, args.expected_sha256, args.mode, deadline) != snapshot:
            raise SwitchError("snapshot manifest changed after preflight; account save was not sent")
        params = {"pluginPath": snapshot["pluginPath"]}
        if remote_id:
            params["remotePluginId"] = remote_id
        else:
            params.update(discoverability="PRIVATE", shareTargets=[])
        result = server.call("plugin/share/save", params)
        returned = result.get("remotePluginId")
        if not isinstance(returned, str) or not returned:
            raise SwitchError("save response has no verified remotePluginId; no retry is allowed")
        state.update(status="unverified", responseRemotePluginId=returned,
                     responseSchemaVerified=isinstance(result.get("shareUrl"), str))
        original = write_mapping(path, manifest, original)  # Retain the real response ID even if the next check fails.
        if ((remote_id and returned != remote_id) or (not remote_id and any(
                item.get("remotePluginId") == returned for item in catalog))):
            raise SwitchError("save returned an unexpected account object; original mapping was not replaced")
        source.update(remotePluginId=returned, version=snapshot["version"], packageName=package_name)
        original = write_mapping(path, manifest, original)
        if not isinstance(result.get("shareUrl"), str):
            raise SwitchError("save response is incomplete; object recorded but not verified")
        visibility_deadline = min(deadline, time.monotonic() + min(args.ready_timeout, 10))
        report["directoryReads"] = 0
        while True:
            remaining = visibility_deadline - time.monotonic()
            if remaining <= 0:
                raise SwitchError("account directory visibility timeout; response ID retained and no save retry is allowed")
            report["directoryReads"] += 1
            catalog = account_inventory(server, timeout=remaining)
            if any(item.get("remotePluginId") == returned for item in catalog):
                # Only absence can be transient. Identity, version or permission conflicts stop immediately.
                report["after"] = account_object(catalog, returned, package_name, snapshot["version"])
                break
            remaining = visibility_deadline - time.monotonic()
            if remaining <= 0:
                raise SwitchError("account directory visibility timeout; response ID retained and no save retry is allowed")
            time.sleep(min(args.poll_interval, remaining))
        state.update(status="verified", permissions=report["after"]["permissions"])
        original = write_mapping(path, manifest, original)
        report["status"] = "saved"
        report["runtimeVerification"] = "not installed or loaded; dot discovery remains a separate verification"
        return 0
    except (SwitchError, OSError, ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        report["error"] = str(error)
        if report.get("saveState"):
            report["status"] = "unknown" if report["saveState"]["status"] == "pending" else "unverified"
        if report.get("publicationStatus") == "published":
            report["partialSuccess"] = True
        return 1
    finally:
        try:
            if server:
                server.close()
        except (OSError, subprocess.SubprocessError) as error:
            report["cleanupError"] = str(error)
        if report["status"] in ("unknown", "unverified") and report.get("operation") and getattr(args, "delivery_directory", None):
            report["retainedDirectory"] = str(args.delivery_directory)
        print(json.dumps(report, ensure_ascii=False), flush=True)
        if report.get("cleanupError"):
            return 1


def published_account_release(project: Path, snapshot: dict, deadline: float) -> dict:
    """Read published facts; local tags alone are not publication proof."""
    repository = github_repository_identity(project)
    if repository != snapshot["metadataSource"]["repository"]:
        raise SwitchError("account artifact repository differs from the target release repository")
    ref = snapshot["releaseRef"]
    tag = validate_release_tag(ref.removeprefix("refs/tags/"))
    release = subprocess.run(
        [shutil.which("gh") or "gh", "release", "view", tag, "--repo", repository,
         "--json", "tagName,isDraft,isPrerelease,publishedAt,url"],
        cwd=project, check=False, text=True, capture_output=True, timeout=remaining_timeout(30, deadline),
    )
    if release.returncode:
        raise SwitchError("published GitHub Release is unavailable; account delivery was not sent")
    metadata = json.loads(release.stdout)
    if (metadata.get("tagName") != tag or metadata.get("isDraft") is not False
            or metadata.get("isPrerelease") is not False or not metadata.get("publishedAt")):
        raise SwitchError("account delivery requires the exact published non-prerelease GitHub Release")
    remote = subprocess.run(
        ["git", "-C", str(project), "ls-remote", "--tags", "origin", ref, ref + "^{}"],
        check=False, text=True, capture_output=True, timeout=remaining_timeout(30, deadline),
    )
    if remote.returncode:
        raise SwitchError("published release tag lookup failed; account delivery was not sent")
    references = dict(reversed(line.split()) for line in remote.stdout.splitlines() if len(line.split()) == 2)
    commit = references.get(ref + "^{}", references.get(ref))
    if commit != snapshot["sourceCommit"]:
        raise SwitchError("published tag commit differs from the reviewed release artifact")
    return {"tag": tag, "tagCommit": commit, "url": metadata.get("url"), "publishedAt": metadata["publishedAt"],
            "ciVerification": "release workflow success must be confirmed through the existing publish flow"}


def unpack_delivery_bundle(bundle: Path, destination: Path, deadline: float) -> Path:
    """Unpack one transport container into a newly owned directory, never into user contents."""
    if bundle.is_symlink() or not bundle.is_file() or bundle.stat().st_size > 500_000_000:
        raise SwitchError("delivery bundle is not a bounded regular file")
    with tarfile.open(bundle, "r:") as archive:
        members = archive.getmembers()
        total = bundle.stat().st_size
        seen = set()
        for member in members:
            remaining_timeout(120, deadline)
            relative = PurePosixPath(member.name)
            name = relative.as_posix()
            if (relative.is_absolute() or ".." in relative.parts or "\\" in member.name or ":" in member.name
                    or name in seen or member.size < 0 or not (member.isfile() or member.isdir())):
                raise SwitchError("delivery bundle contains an unsafe path or file type")
            seen.add(name)
            total += member.size
            if total > 500_000_000:
                raise SwitchError("delivery bundle exceeds the bounded extraction budget")
        def bounded_data_filter(member: tarfile.TarInfo, target: str) -> tarfile.TarInfo | None:
            remaining_timeout(120, deadline)
            return tarfile.data_filter(member, target)
        archive.extractall(destination, members=members, filter=bounded_data_filter)
        remaining_timeout(120, deadline)
    manifest = destination / "snapshots.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise SwitchError("delivery bundle has no regular snapshots.json")
    return manifest


def run_account_delivery(args: argparse.Namespace) -> int:
    args.deadline = time.monotonic() + 600
    args.cwd = str(args.project)
    lock = None
    staging = None
    try:
        if args.action == "save-account":
            root = Path(args.delivery_dir)
            if root.is_symlink():
                raise SwitchError("delivery directory must not be a symbolic link")
            root.mkdir(exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".release-account-", dir=root.resolve()))
            args.delivery_directory = staging
            args.snapshots = str(unpack_delivery_bundle(Path(args.bundle), staging, args.deadline))
        if args.apply:
            path = Path(args.manifest).resolve()
            lock_path = path.with_name(path.name + ".lock")
            lock = lock_path.open("x", encoding="utf-8")
        return save_account(args)
    except (SwitchError, OSError, ValueError, OverflowError, tarfile.TarError) as error:
        print(json.dumps({"plugin": args.plugin, "target": args.mode, "action": args.action,
                          "status": "blocked", "error": str(error)}, ensure_ascii=False), flush=True)
        return 1
    finally:
        cleanup_failed = False
        if lock:
            try:
                lock.close()
                lock_path.unlink()
            except OSError as error:
                print(json.dumps({"event": "mapping_lock_cleanup_failed", "status": "failed", "error": str(error)}), flush=True)
                cleanup_failed = True
        report = getattr(args, "delivery_report", {})
        retain = report.get("status") in ("unknown", "unverified") and report.get("operation")
        if staging is not None and not retain:
            try:
                shutil.rmtree(staging)
            except OSError as error:
                print(json.dumps({"event": "delivery_directory_cleanup_failed", "status": "failed", "error": str(error)}), flush=True)
                cleanup_failed = True
        if cleanup_failed:
            return 1


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
    preflight.add_argument(
        "--allow-existing-release",
        action="store_true",
        help="CI 重试时允许已存在的同名远端标签或发布记录。",
    )
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
    for name in ("deliver-account", "reconcile-account"):
        account = subparsers.add_parser(name, help="在已登录环境交付正式账号内容或只读核对已有回执。")
        account.set_defaults(action="save-account" if name == "deliver-account" else "reconcile-account", mode="RELEASE")
        account.add_argument("--project", type=Path, default=Path.cwd())
        account.add_argument("--manifest", required=True)
        account.add_argument("--plugin", required=True)
        account.add_argument("--apply", action="store_true", help="应用已明确授权的精确交付或本地对账状态修正。")
        account.add_argument("--timeout", type=float, default=30)
        account.add_argument("--ready-timeout", type=float, default=60)
        account.add_argument("--poll-interval", type=float, default=1)
        if name == "deliver-account":
            account.add_argument("--bundle", required=True, help="正式流水线的单一 tar 交付产物。")
            account.add_argument("--delivery-dir", required=True, help="明确授权解包的本机目录。")
            account.add_argument("--expected-sha256", required=True)
        else:
            account.add_argument("--mode", choices=("DEV", "RELEASE"), default="RELEASE", help="DEV 只用于历史回执恢复。")
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
    if args.command in ("deliver-account", "reconcile-account"):
        return run_account_delivery(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
