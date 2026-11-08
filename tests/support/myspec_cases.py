"""Pure MySpec document constructors shared by ordinary and installed checks."""
from __future__ import annotations

from pathlib import Path


def bumped_patch(version: str, amount: int = 1) -> str:
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + amount}"



def requirement(title: str, behavior: str, scenario: str = "正常流程") -> str:
    return f"""### Requirement: {title}

系统 MUST {behavior}。

#### Scenario: {scenario}

- **WHEN** 用户执行操作
- **THEN** 系统返回结果
"""



def main_spec(capability: str, *requirements: str) -> str:
    return f"""# {capability}

## Purpose

描述 {capability} 的外部行为。

## Requirements

{"\n".join(requirements)}"""



def npm_prefix_for(installed_package: Path) -> Path:
    node_modules = installed_package.parents[1]
    return node_modules.parent.parent if node_modules.parent.name == "lib" else node_modules.parent

