#!/usr/bin/env bash
set -euo pipefail

export PATH="/c/Program Files/Git/cmd:$PATH"

PYTHON_EXE="/c/Users/liuli/AppData/Local/Programs/Python/Python312/python.exe"
if [ ! -x "$PYTHON_EXE" ]; then
  PYTHON_EXE="python"
fi

"$PYTHON_EXE" -m pytest \
  tests/test_release_flow_plugin_package.py \
  tests/test_release_flow_cli.py \
  tests/test_agent_guard_plugin_package.py \
  tests/test_agent_guard_plugin_installer.py \
  tests/test_cross_agent_review_plugin_package.py \
  tests/test_cross_agent_review_cli.py \
  -q
