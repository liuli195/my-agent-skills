from __future__ import annotations

import runpy
from pathlib import Path


runpy.run_path(
    Path(__file__).resolve().parents[3] / "python" / "spec_ops.py",
    run_name="__main__",
)
