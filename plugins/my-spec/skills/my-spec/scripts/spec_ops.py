from __future__ import annotations

import runpy
import sys
from pathlib import Path


python_root = Path(__file__).resolve().parents[3] / "python"
sys.path.insert(0, str(python_root))
runpy.run_path(
    python_root / "spec_ops.py",
    run_name="__main__",
)
