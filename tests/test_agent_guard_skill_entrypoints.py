from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "agent-guard"
SOURCE_SKILL = PLUGIN_ROOT / "skills" / "agent-guard"
ENTRYPOINT_SKILLS = [
    "agent-guard-install",
    "agent-guard-init",
    "agent-guard-update",
    "agent-guard-run",
]
ENTRYPOINT_REFERENCES = {
    "agent-guard-install": ["research-and-extract.md", "profile-draft.md"],
    "agent-guard-init": ["init-flow.md", "init-boundaries.md"],
    "agent-guard-update": ["runtime-update.md", "profile-sync.md"],
    "agent-guard-run": ["activate.md", "brief.md", "events.md", "close.md"],
}


def skill_description(skill_path: Path) -> str:
    text = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    in_frontmatter = False
    for line in lines:
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            break
        if in_frontmatter and line.startswith("description:"):
            return line.removeprefix("description:").strip()
    raise AssertionError("SKILL.md missing frontmatter description")


def test_agent_guard_router_description_covers_routing_triggers() -> None:
    description = skill_description(SOURCE_SKILL)

    for term in [
        "路由",
        "Use when",
        "agent-guard",
        "install/init/update/run",
    ]:
        assert term in description
    for term in ["Guard Profile（守卫画像）", "Guard Runtime（守卫运行时）", "Hook（钩子）"]:
        assert term not in description


def test_agent_guard_router_points_to_scenario_entrypoints() -> None:
    skill_text = (SOURCE_SKILL / "SKILL.md").read_text(encoding="utf-8")

    assert "薄路由" in skill_text
    for entrypoint in ENTRYPOINT_SKILLS:
        assert f"${entrypoint}" in skill_text
    assert "$agent-guard-hooks" not in skill_text


def test_scenario_entrypoints_have_strong_required_steps() -> None:
    required_phrases = {
        "agent-guard-install": [
            "安装守卫",
            "立即执行：在调研、生成或更新任何 Guard Profile（守卫画像）前，使用 Skill 工具加载 `$grill-with-docs`。禁止跳过此步骤。",
            "references/research-and-extract.md",
            "references/profile-draft.md",
        ],
        "agent-guard-init": [
            "初始化守卫",
            "立即执行：在初始化任何项目级或用户级 Guard Profile（守卫画像）前，运行 `validate_guard_profile.py <guard-profile-dir>`。禁止跳过此步骤。",
            "references/init-flow.md",
            "references/init-boundaries.md",
        ],
        "agent-guard-update": [
            "更新守卫",
            "立即执行：在把更新后的 Guard Profile（守卫画像）同步到已初始化守卫前，运行 `validate_guard_profile.py <guard-profile-dir>`。禁止跳过此步骤。",
            "references/runtime-update.md",
            "references/profile-sync.md",
        ],
        "agent-guard-run": [
            "运行守卫",
            "立即执行：提交任何 `state_completed` 事件前，读取当前 Session Focus Instance（会话焦点实例）的最新 Guard Brief（守卫简报）。禁止跳过此步骤。",
            "references/activate.md",
            "references/brief.md",
            "references/events.md",
            "references/close.md",
        ],
    }

    for entrypoint, phrases in required_phrases.items():
        skill_dir = SOURCE_SKILL.parent / entrypoint
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        description = skill_description(skill_dir)
        assert "Use when" in description
        for phrase in phrases:
            assert phrase in skill_text
        for reference_name in ENTRYPOINT_REFERENCES[entrypoint]:
            assert (skill_dir / "references" / reference_name).exists()
        for shared_dir in ["scripts", "assets"]:
            assert not (skill_dir / shared_dir).exists()


def test_core_references_are_common_and_scenario_docs_live_with_entrypoints() -> None:
    core_references = SOURCE_SKILL / "references"

    for reference_name in [
        "architecture.md",
        "terminology.md",
        "template-index.md",
    ]:
        assert (core_references / reference_name).exists()

    for obsolete_name in [
        "subject-resolution.md",
        "extraction-method.md",
        "guard-profile.md",
        "runtime-contract.md",
        "hook-contract.md",
        "guard-injection.md",
        "codex-claude-compat.md",
    ]:
        assert not (core_references / obsolete_name).exists()

    for entrypoint, reference_names in ENTRYPOINT_REFERENCES.items():
        entrypoint_references = SOURCE_SKILL.parent / entrypoint / "references"
        assert entrypoint_references.is_dir()
        for reference_name in reference_names:
            assert (entrypoint_references / reference_name).exists()


def test_global_command_guard_docs_are_scenario_oriented() -> None:
    paths = [
        SOURCE_SKILL / "SKILL.md",
        SOURCE_SKILL / "references" / "template-index.md",
        SOURCE_SKILL.parent / "agent-guard-install" / "SKILL.md",
        SOURCE_SKILL.parent / "agent-guard-install" / "references" / "profile-draft.md",
        SOURCE_SKILL.parent / "agent-guard-init" / "SKILL.md",
        SOURCE_SKILL.parent / "agent-guard-init" / "references" / "init-flow.md",
        SOURCE_SKILL.parent / "agent-guard-update" / "SKILL.md",
        SOURCE_SKILL.parent / "agent-guard-update" / "references" / "profile-sync.md",
        SOURCE_SKILL.parent / "agent-guard-run" / "SKILL.md",
        SOURCE_SKILL.parent / "agent-guard-run" / "references" / "events.md",
    ]
    combined_text = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for phrase in [
        "Global Command Guard",
        "global-command-guards.yaml",
        "artifacts.yaml",
        "artifact",
        "禁止新增 reviewed wrapper",
        "external artifact（外部产物）",
        "禁止在 Agent Guard 中实现 cross-agent-review 内部流程",
        "禁止把 `verify --apply` 作为主拦截点",
        "`deny.reason`、`deny.next` 和 `deny.suggestion` 可以在 Guard Profile",
        "Runtime（运行时）只透传或渲染，不内置业务流程",
        "install",
        "init",
        "update",
        "run",
        "troubleshoot",
    ]:
        assert phrase in combined_text


def test_templates_do_not_include_python_cache_artifacts() -> None:
    templates_root = SOURCE_SKILL / "assets" / "templates"

    assert not list(templates_root.rglob("__pycache__"))
    assert not list(templates_root.rglob("*.pyc"))
