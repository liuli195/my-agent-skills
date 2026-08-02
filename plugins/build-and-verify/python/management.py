from __future__ import annotations

from pathlib import Path
import sys

sys.dont_write_bytecode = True

_MANAGEMENT = Path(__file__).resolve().parents[2] / "tool-lifecycle" / "python" / "management.py"
exec(compile(_MANAGEMENT.read_text(encoding="utf-8"), str(_MANAGEMENT), "exec"), globals())
