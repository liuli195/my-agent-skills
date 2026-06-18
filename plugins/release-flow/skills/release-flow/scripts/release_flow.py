"""Release Flow Plugin（发布流程插件）命令行入口。"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

import yaml


SCRIPT_PATH = Path(__file__).resolve()
SKILL_ROOT = SCRIPT_PATH.parents[1]
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "templates"

FORBIDDEN_VARIABLE_VALUE_KEYS = {"value", "secret", "defaultValue", "default_value"}
SUPPORTED_VARIABLE_SOURCE = "github-actions-variable"
SUPPORTED_TRANSFORM_TYPE = "json-env"
SUPPORTED_GENERATOR_TYPE = "codex-marketplace"
SUPPORTED_GENERATOR_IDENTITY = "codex"
SUPPORTED_CODEX_MARKETPLACE_PLUGINS = {"agent-guard", "release-flow"}
SETUP_TARGETS = [
    ("release-flow/config.yaml", ".release-flow/config.yaml"),
    ("release-flow/projection.yaml", ".release-flow/projection.yaml"),
    ("release-flow/gitignore", ".release-flow/.gitignore"),
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
    records_directory: str
    manifest_version_files: list[str]
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
class ProjectionReleaseFlowPluginIdentity:
    repository_variable: str
    ref_variable: str


@dataclass(frozen=True)
class ProjectionIdentity:
    codex: ProjectionCodexIdentity
    claude: ProjectionClaudeIdentity
    release_flow_plugin: ProjectionReleaseFlowPluginIdentity


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

    records = data.get("records")
    if not isinstance(records, dict):
        raise ValueError("invalid_config: records must be mapping")
    records_directory = records.get("directory")
    if records_directory != ".release-flow/releases":
        raise ValueError("invalid_config: records.directory must be .release-flow/releases")

    manifests = data.get("manifests")
    if not isinstance(manifests, dict):
        raise ValueError("invalid_config: manifests must be mapping")
    manifest_version_files = manifests.get("versionFiles")
    if not isinstance(manifest_version_files, list) or not all(
        isinstance(item, str) for item in manifest_version_files
    ):
        raise ValueError("invalid_config: manifests.versionFiles must be string list")

    return FlowConfig(
        path=path,
        version=version,
        release_source_ref=release_source_ref,
        release_channel_branch=release_channel_branch,
        release_branch_mode=release_branch_mode,
        workflow_file=workflow_file,
        workflow_trigger=workflow_trigger,
        records_directory=records_directory,
        manifest_version_files=manifest_version_files,
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
    release_flow_plugin_data = identity_data.get("releaseFlowPlugin")
    if not isinstance(release_flow_plugin_data, dict):
        raise ValueError("projection_identity_release_flow_plugin_invalid")

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
        release_flow_plugin=ProjectionReleaseFlowPluginIdentity(
            repository_variable=require_string(
                release_flow_plugin_data,
                "repositoryVariable",
                "projection_identity_missing: identity.releaseFlowPlugin.repositoryVariable",
            ),
            ref_variable=require_string(
                release_flow_plugin_data,
                "refVariable",
                "projection_identity_missing: identity.releaseFlowPlugin.refVariable",
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
        "identity.releaseFlowPlugin.repositoryVariable": (
            projection.identity.release_flow_plugin.repository_variable
        ),
        "identity.releaseFlowPlugin.refVariable": projection.identity.release_flow_plugin.ref_variable,
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


def required_github_variable_details(projection: Projection) -> list[ProjectionVariable]:
    return [
        variable
        for variable in projection.variables.values()
        if variable.source == SUPPORTED_VARIABLE_SOURCE and variable.required
    ]


def projection_identity_variable_errors(
    projection: Projection, variable_name: str
) -> list[str]:
    variable = projection.variables.get(variable_name)
    if variable is None:
        return [f"projection_identity_variable_missing: {variable_name}"]
    errors: list[str] = []
    if variable.source != SUPPORTED_VARIABLE_SOURCE:
        errors.append(f"projection_identity_variable_source_unsupported: {variable_name}")
    if not variable.required:
        errors.append(f"projection_identity_variable_not_required: {variable_name}")
    return errors


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
    if projection.identity is not None:
        errors.extend(
            projection_identity_variable_errors(
                projection,
                projection.identity.release_flow_plugin.repository_variable,
            )
        )
        errors.extend(
            projection_identity_variable_errors(
                projection,
                projection.identity.release_flow_plugin.ref_variable,
            )
        )
    for generator in projection.generators:
        if generator.type != SUPPORTED_GENERATOR_TYPE:
            errors.append(f"projection_generator_type_unsupported: {generator.path}")
        if generator.identity != SUPPORTED_GENERATOR_IDENTITY:
            errors.append(f"projection_generator_identity_unsupported: {generator.path}")
        if projection.identity is None:
            errors.append(f"projection_generator_identity_missing: {generator.path}")
        for plugin_name in generator.plugins:
            if plugin_name not in SUPPORTED_CODEX_MARKETPLACE_PLUGINS:
                errors.append(f"projection_generator_plugin_unknown: {plugin_name}")
    for transform in projection.transforms:
        if transform.type != SUPPORTED_TRANSFORM_TYPE:
            errors.append(f"projection_transform_type_unsupported: {transform.path}")
        for pointer, variable_name in transform.set.items():
            if variable_name not in projection.variables:
                errors.append(f"projection_transform_variable_unknown: {variable_name}")
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
    entries = {
        "agent-guard": {
            "name": "agent-guard",
            "source": {"source": "local", "path": "./plugins/agent-guard"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        },
        "release-flow": {
            "name": "release-flow",
            "source": {"source": "local", "path": "./plugins/release-flow"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        },
    }
    try:
        return entries[plugin_name]
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


def apply_json_env_transform(project: Path, transform: ProjectionTransform, vars_data: dict[str, Any]) -> None:
    target_path = resolve_project_path(project, transform.path, "invalid_projection_transform_path")
    target = read_json_mapping(target_path)
    for pointer, variable_name in transform.set.items():
        if variable_name not in vars_data:
            raise ValueError(f"projection_variable_missing: {variable_name}")
        set_json_pointer(target, pointer, vars_data[variable_name])
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
        vars_data = read_json_mapping(args.vars_file)
        apply_projection(args.project, projection, vars_data)
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
    rulesets_enabled = github_config_value(config, ["rulesets", "enabled"], True)
    branch_protection_fallback = github_config_value(
        config, ["rulesets", "branchProtectionFallback"], False
    )

    print("status: github_plan")
    print(f"actions_workflow_permissions: {workflow_permissions}")
    print(f"rulesets: {'required' if rulesets_enabled else 'not_required'}")
    print(f"branch_protection_fallback: {str(bool(branch_protection_fallback)).lower()}")
    print("actions_variables:")
    for variable in projection.variables.values():
        if variable.source == SUPPORTED_VARIABLE_SOURCE:
            print(f"  - {variable.name}")
            print(f"    required: {str(variable.required).lower()}")
            description = variable.raw.get("description")
            if isinstance(description, str):
                print(f"    description: {description}")
            expected = variable.raw.get("expected")
            if isinstance(expected, str):
                print(f"    expected: {expected}")
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
    rulesets_enabled = github_config_value(config, ["rulesets", "enabled"], True)
    variables = [
        variable
        for variable in projection.variables.values()
        if variable.source == SUPPORTED_VARIABLE_SOURCE
    ]

    if args.dry_run:
        print("status: manual_steps")
        print(f"project: {args.project}")
        print(f"Set Actions workflow permissions to {workflow_permissions}")
        if rulesets_enabled:
            print("Create Rulesets for main, marketplace, and tags")
        else:
            print("Rulesets are disabled in release-flow config")
        print("Create GitHub Actions Variables")
        for variable in variables:
            print(f"  - {variable.name}")
            print(f"    required: {str(variable.required).lower()}")
            description = variable.raw.get("description")
            if isinstance(description, str):
                print(f"    description: {description}")
            expected = variable.raw.get("expected")
            if isinstance(expected, str):
                print(f"    expected: {expected}")
            if variable.required:
                print(f"Set GitHub Actions Variable {variable.name}")
        return 0

    print("status: issues")
    print("error: github_write_not_available_without_repository_context")
    return 2


def release_plan_path(project: Path, config: FlowConfig, tag: str) -> Path:
    safe_tag = validate_release_tag(tag)
    return project / config.records_directory / safe_tag / "release-plan.json"


def read_release_plan(project: Path, config: FlowConfig, tag: str) -> dict[str, Any]:
    plan_path = release_plan_path(project, config, tag)
    try:
        return read_json_mapping(plan_path)
    except ValueError as exc:
        if str(exc).startswith("missing_file:"):
            raise ValueError(f"missing_release_plan: {tag}") from exc
        raise


def tag_version(tag: str) -> str:
    validate_release_tag(tag)
    if tag.startswith("v") and len(tag) > 1:
        return tag[1:]
    return tag


def manifest_versions(project: Path, config: FlowConfig) -> dict[str, str]:
    versions: dict[str, str] = {}
    for manifest_file in config.manifest_version_files:
        manifest_relative_path = Path(manifest_file)
        manifest_path = resolve_project_path(project, manifest_relative_path, "invalid_manifest_path")
        manifest = read_json_mapping(manifest_path)
        version = manifest.get("version")
        if not isinstance(version, str):
            raise ValueError(f"manifest_version_missing: {manifest_file}")
        versions[manifest_file.replace("\\", "/")] = version
    return versions


def run_release_init(args: argparse.Namespace) -> int:
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

    try:
        plan_path = release_plan_path(args.project, config, args.tag)
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    if plan_path.exists() and not args.replace:
        print("status: issues")
        print(f"error: release_plan_exists: {args.tag}")
        return 1

    plan = {
        "version": args.version,
        "tag": args.tag,
        "sourceRef": config.release_source_ref,
        "channelBranch": config.release_channel_branch,
        "workflowFile": config.workflow_file,
        "projectionRegistry": str(projection.path.relative_to(args.project)).replace("\\", "/"),
        "dryRun": bool(args.dry_run),
    }
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("status: release_plan_created")
    print(f"release_plan: {plan_path}")
    return 0


def required_github_variables(projection: Projection) -> list[str]:
    return [variable.name for variable in required_github_variable_details(projection)]


def apply_projection(project: Path, projection: Projection, vars_data: dict[str, Any]) -> None:
    for generator in projection.generators:
        apply_projection_generator(project, projection, generator)
    for transform in projection.transforms:
        apply_json_env_transform(project, transform, vars_data)


def required_variable_report(
    projection: Projection, vars_data: dict[str, Any]
) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for variable in required_github_variable_details(projection):
        expected_reference = variable.raw.get("expected")
        expected_value = expected_variable_value(projection, variable)
        item: dict[str, Any] = {
            "name": variable.name,
            "description": variable.raw.get("description", ""),
            "expected": expected_reference if isinstance(expected_reference, str) else None,
            "expectedValue": expected_value,
            "manualStep": f"Set GitHub Actions Variable {variable.name}",
            "present": variable.name in vars_data,
        }
        report.append(item)
    return report


def identity_variable_errors(projection: Projection, vars_data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for variable in projection.variables.values():
        if variable.name not in vars_data:
            continue
        expected_value = expected_variable_value(projection, variable)
        if expected_value is None:
            continue
        actual_value = str(vars_data[variable.name])
        if actual_value != expected_value:
            errors.append(f"identity_variable_mismatch: {variable.name}")
            errors.append(f"expected: {expected_value}")
            errors.append(f"actual: {actual_value}")
    return errors


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
    return ".release-flow" in relative_path.parts and "releases" in relative_path.parts


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


def dirty_tracked_files(project: Path) -> list[str] | None:
    head = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
    )
    if head.returncode != 0:
        return []
    result = subprocess.run(
        ["git", "-C", str(project), "status", "--porcelain", "--untracked-files=no"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    dirty_files: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        dirty_files.append(line[3:].strip())
    return dirty_files


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
        ignored = {name for name in names if name in {".git", "__pycache__", ".pytest_cache"}}
        if Path(directory).name == ".release-flow":
            ignored.add("releases")
        return ignored

    shutil.copytree(source, target, ignore=ignore)


def tree_file_paths(root: Path) -> set[str]:
    if not root.exists():
        return set()
    ignored_parts = {".git", "__pycache__", ".pytest_cache"}
    paths: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ignored_expected_path(relative):
            continue
        if path.is_file():
            paths.add(relative.as_posix())
    return paths


def unmanaged_channel_diffs(expected_tree: Path, channel_tree: Path) -> list[str]:
    expected_paths = tree_file_paths(expected_tree)
    channel_paths = tree_file_paths(channel_tree)
    diffs: list[str] = []
    for relative_path in sorted(expected_paths | channel_paths):
        expected_path = expected_tree / relative_path
        channel_path = channel_tree / relative_path
        if relative_path not in expected_paths or relative_path not in channel_paths:
            diffs.append(relative_path)
            continue
        if expected_path.read_bytes() != channel_path.read_bytes():
            diffs.append(relative_path)
    return diffs


def preflight_errors(
    project: Path,
    tag: str,
    config: FlowConfig,
    projection: Projection,
    plan: dict[str, Any],
    vars_data: dict[str, Any],
    channel_tree: Path | None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    expected_version = tag_version(tag)
    missing_variables = [
        variable_name
        for variable_name in required_github_variables(projection)
        if variable_name not in vars_data
    ]
    required_variables = required_variable_report(projection, vars_data)
    required_variables_by_name = {item["name"]: item for item in required_variables}
    for variable_name in missing_variables:
        errors.append(f"missing_required_variable: {variable_name}")
        variable_report = required_variables_by_name.get(variable_name, {})
        description = variable_report.get("description")
        if description:
            errors.append(f"variable_description: {description}")
        manual_step = variable_report.get("manualStep")
        if manual_step:
            errors.append(f"manual_step: {manual_step}")

    if not missing_variables:
        errors.extend(identity_variable_errors(projection, vars_data))

    plan_version = plan.get("version")
    if plan.get("tag") != tag:
        errors.append(f"release_plan_tag_mismatch: {tag}")
    if plan_version != expected_version:
        errors.append(f"release_plan_version_mismatch: {tag}")

    versions: dict[str, str] = {}
    mismatched_manifests: list[str] = []
    try:
        versions = manifest_versions(project, config)
        for manifest_file, version in versions.items():
            if version != expected_version:
                mismatched_manifests.append(manifest_file)
                errors.append(f"manifest_version_mismatch: {manifest_file}")
    except ValueError as exc:
        errors.append(str(exc))

    channel_diffs: list[str] = []
    if channel_tree is not None and not errors:
        dirty_files = dirty_tracked_files(project)
        if dirty_files:
            errors.append(f"dirty_tracked_files: {', '.join(dirty_files)}")

    if channel_tree is not None and not errors:
        with tempfile.TemporaryDirectory(prefix="release-flow-preflight-") as temp_dir:
            expected_tree = Path(temp_dir) / "expected"
            copy_project_for_expected(project, expected_tree)
            expected_projection = read_projection(expected_tree)
            apply_projection(expected_tree, expected_projection, vars_data)
            identity_errors = [
                *marketplace_identity_errors(expected_tree, expected_projection),
                *marketplace_identity_errors(channel_tree, expected_projection),
            ]
            if identity_errors:
                errors.extend(identity_errors)
            else:
                channel_diffs = unmanaged_channel_diffs(expected_tree, channel_tree)
        for diff in channel_diffs:
            errors.append(f"unmanaged_channel_diff: {diff}")

    report = {
        "tag": tag,
        "variables": {"missing": missing_variables, "required": required_variables},
        "version": {
            "expected": expected_version,
            "releasePlan": plan_version,
            "manifests": versions,
            "mismatchedManifests": mismatched_manifests,
        },
        "channel": {"unmanagedDiffs": channel_diffs},
    }
    return errors, report


def run_preflight(args: argparse.Namespace) -> int:
    try:
        config = read_config(args.project)
        projection = read_projection(args.project)
        errors = projection_errors(projection)
        if errors:
            raise ValueError(errors[0])
        plan = read_release_plan(args.project, config, args.tag)
        vars_data = read_json_mapping(args.github_vars_file) if args.github_vars_file else {}
        errors, report = preflight_errors(
            args.project,
            args.tag,
            config,
            projection,
            plan,
            vars_data,
            args.channel_tree,
        )
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    if errors:
        print("status: issues")
        for error in errors:
            print(f"error: {error}")
        return 1

    report_path = release_plan_path(args.project, config, args.tag).parent / "preflight-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("status: preflight_passed")
    print(f"preflight_report: {report_path}")
    return 0


def workflow_dispatch_command(config: FlowConfig, tag: str, version: str) -> str:
    validate_release_tag(tag)
    release_plan = f".release-flow/releases/{tag}/release-plan.json"
    return (
        f"gh workflow run {config.workflow_file} -f tag={tag} "
        f"-f version={version} -f releasePlan={release_plan}"
    )


def run_publish(args: argparse.Namespace) -> int:
    try:
        config = read_config(args.project)
        plan = read_release_plan(args.project, config, args.tag)
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    if not args.dry_run and not args.authorize_publish:
        print("status: issues")
        print("error: publish_requires_authorize_publish")
        return 2

    plan_version = plan.get("version")
    if not isinstance(plan_version, str):
        print("status: issues")
        print(f"error: release_plan_version_missing: {args.tag}")
        return 1

    command = workflow_dispatch_command(config, args.tag, plan_version)
    if args.dry_run:
        print("status: dry_run")
        print(f"tag: {plan.get('tag', args.tag)}")
        print(f"workflow_dispatch: {command}")
        print("local_branch: not_created")
        print("tag: not_created")
        print("push: not_run")
        return 0

    result = subprocess.run(command.split(), check=False, text=True)
    return result.returncode


def release_record_directory(project: Path, config: FlowConfig, tag: str) -> Path:
    return release_plan_path(project, config, tag).parent


def release_summary_markdown(tag: str, plan: dict[str, Any], workflow_run: dict[str, Any]) -> str:
    lines = [
        f"# Release {tag}",
        "",
        f"- tag: {tag}",
        f"- version: {plan.get('version', '')}",
        f"- conclusion: {workflow_run.get('conclusion', '')}",
        f"- GitHub Release URL: {workflow_run.get('releaseUrl', '')}",
        f"- marketplace commit: {workflow_run.get('marketplaceCommit', '')}",
        f"- workflow run: {workflow_run.get('url', '')}",
        f"- workflow run databaseId: {workflow_run.get('databaseId', '')}",
        "",
    ]
    variables = workflow_run.get("variables", {})
    if isinstance(variables, dict) and variables:
        lines.append("## Variables")
        for name, value in sorted(variables.items()):
            lines.append(f"- {name}: {value}")
        lines.append("")
    return "\n".join(lines)


def run_summarize(args: argparse.Namespace) -> int:
    try:
        config = read_config(args.project)
        plan = read_release_plan(args.project, config, args.tag)
        workflow_run = read_json_mapping(args.workflow_run_file)
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    record_directory = release_record_directory(args.project, config, args.tag)
    workflow_run_path = record_directory / "workflow-run.json"
    summary_path = record_directory / "release-summary.md"
    workflow_run_path.write_text(
        json.dumps(workflow_run, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        release_summary_markdown(args.tag, plan, workflow_run),
        encoding="utf-8",
    )

    print("status: summarized")
    print(f"workflow_run: {workflow_run_path}")
    print(f"release_summary: {summary_path}")
    return 0


def resolve_release_plan_arg(project: Path, config: FlowConfig, tag: str, release_plan: Path) -> Path:
    validate_release_tag(tag)
    expected_path = release_plan_path(project, config, tag).resolve()
    if release_plan.is_absolute() or not is_relative_path_inside_project(release_plan):
        raise ValueError(f"invalid_release_plan_path: {release_plan}")
    resolved_path = resolve_project_path(project, release_plan, "invalid_release_plan_path").resolve()
    if resolved_path != expected_path:
        raise ValueError(f"invalid_release_plan_path: {release_plan}")
    return resolved_path


def copy_project_for_ci_publish(source: Path, target: Path) -> None:
    def ignore(directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in {".git", "__pycache__", ".pytest_cache"}}

    shutil.copytree(source, target, ignore=ignore)


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


def release_branch_name(tag: str) -> str:
    safe_tag = validate_release_tag(tag)
    return f"release-flow-{safe_tag}"


def run_ci_publish_remote(project: Path, config: FlowConfig, projection: Projection, tag: str, vars_data: dict[str, Any]) -> None:
    branch_name = release_branch_name(tag)
    run_checked(["git", "config", "user.name", "github-actions[bot]"], project)
    run_checked(
        [
            "git",
            "config",
            "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com",
        ],
        project,
    )
    run_checked(["git", "checkout", "--orphan", branch_name], project)
    shutil.rmtree(project / ".release-flow" / "releases", ignore_errors=True)
    apply_projection(project, projection, vars_data)
    run_checked(["git", "add", "-A"], project)
    run_checked(["git", "commit", "-m", f"release: {tag}"], project)
    run_checked(
        ["git", "push", "origin", f"HEAD:refs/heads/{config.release_channel_branch}", "--force"],
        project,
    )
    run_checked(["git", "tag", "--", tag], project)
    run_checked(["git", "push", "origin", f"refs/tags/{tag}"], project)
    run_checked(["gh", "release", "create", tag, "--title", tag, "--notes", f"Release {tag}"], project)


def run_ci_publish(args: argparse.Namespace) -> int:
    if not args.dry_run and not args.authorize_ci_publish:
        print("status: issues")
        print("error: ci_publish_requires_authorize_ci_publish")
        return 2

    try:
        config = read_config(args.project)
        projection = read_projection(args.project)
        errors = projection_errors(projection)
        if errors:
            raise ValueError(errors[0])
        release_plan_path_arg = resolve_release_plan_arg(args.project, config, args.tag, args.release_plan)
        plan = read_json_mapping(release_plan_path_arg)
        vars_data = read_json_mapping(args.vars_file)
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    if plan.get("tag") != args.tag:
        print("status: issues")
        print(f"error: release_plan_tag_mismatch: {args.tag}")
        return 1

    if args.dry_run:
        projected_project = args.project.parent / f"{args.project.name}-projected"
        if projected_project.exists():
            print("status: issues")
            print(f"error: projected_directory_exists: {projected_project}")
            return 1

        try:
            copy_project_for_ci_publish(args.project, projected_project)
            projected_projection = read_projection(projected_project)
            apply_projection(projected_project, projected_projection, vars_data)
        except ValueError as exc:
            print("status: issues")
            print(f"error: {exc}")
            return 1

        print("status: ci_dry_run")
        print(f"projected_project: {projected_project}")
        print(f"channel_branch: {config.release_channel_branch}")
        print(f"tag: {args.tag}")
        print("remote_write: not_run")
        return 0

    try:
        run_ci_publish_remote(args.project, config, projection, args.tag, vars_data)
    except ValueError as exc:
        print("status: issues")
        print(f"error: {exc}")
        return 1

    print("status: ci_published")
    print(f"channel_branch: {config.release_channel_branch}")
    print(f"tag: {args.tag}")
    print("remote_write: completed")
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
    project.add_argument("--vars-file", type=Path, required=True, help="变量 JSON 文件。")
    github_plan = subparsers.add_parser("github-plan", help="输出 GitHub release-flow 配置计划。")
    github_plan.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    configure_github = subparsers.add_parser("configure-github", help="输出或执行 GitHub release-flow 配置。")
    configure_github.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    configure_github.add_argument("--dry-run", action="store_true", help="只输出手动配置步骤。")
    configure_github.add_argument("--authorize-github", action="store_true", help="授权写入 GitHub 配置。")
    release_init = subparsers.add_parser("release-init", help="创建 release plan。")
    release_init.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    release_init.add_argument("--tag", required=True, help="发布标签。")
    release_init.add_argument("--version", required=True, help="发布版本。")
    release_init.add_argument("--dry-run", action="store_true", help="标记 release plan 为 dry run。")
    release_init.add_argument("--replace", action="store_true", help="覆盖已有 release plan。")
    preflight = subparsers.add_parser("preflight", help="执行 release-flow 发布前检查。")
    preflight.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    preflight.add_argument("--tag", required=True, help="发布标签。")
    preflight.add_argument("--github-vars-file", type=Path, help="GitHub Actions variables JSON 文件。")
    preflight.add_argument("--channel-tree", type=Path, help="本地 channel tree 目录。")
    publish = subparsers.add_parser("publish", help="触发 GitHub release workflow。")
    publish.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    publish.add_argument("--tag", required=True, help="发布标签。")
    publish.add_argument("--dry-run", action="store_true", help="只打印 workflow dispatch 命令。")
    publish.add_argument("--authorize-publish", action="store_true", help="授权触发 GitHub 发布。")
    summarize = subparsers.add_parser("summarize", help="写入 release workflow 摘要记录。")
    summarize.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    summarize.add_argument("--tag", required=True, help="发布标签。")
    summarize.add_argument("--workflow-run-file", type=Path, required=True, help="workflow run JSON 文件。")
    ci_publish = subparsers.add_parser("ci-publish", help="CI 中发布 release channel。")
    ci_publish.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目根目录。")
    ci_publish.add_argument("--tag", required=True, help="发布标签。")
    ci_publish.add_argument("--release-plan", type=Path, required=True, help="release plan 路径。")
    ci_publish.add_argument("--vars-file", type=Path, required=True, help="变量 JSON 文件。")
    ci_publish.add_argument("--dry-run", action="store_true", help="只执行本地 projection 演练。")
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
    if args.command == "release-init":
        return run_release_init(args)
    if args.command == "preflight":
        return run_preflight(args)
    if args.command == "publish":
        return run_publish(args)
    if args.command == "summarize":
        return run_summarize(args)
    if args.command == "ci-publish":
        return run_ci_publish(args)
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
