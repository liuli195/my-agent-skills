## 1. Contract Tests

- [x] 1.1 Add repository-wide Python AST（Python 语法树） test scan for ordinary tests using real subprocess（子进程）, CLI（命令行） entrypoints, temporary git（版本控制）, or broad cache（缓存） scans, including this repository's existing helper（辅助函数） and fixture（测试夹具） shapes.
- [x] 1.2 Add a narrow E2E（端到端测试） allowlist by test function identity（测试函数身份） with documented reasons.
- [x] 1.3 Add focused checks that build-and-verify（构建与验证） keeps one init（初始化） E2E（端到端测试） and one verify（验证） E2E（端到端测试）.

## 2. Minimal Test Refactor

- [x] 2.1 Convert repeated build-and-verify（构建与验证） branch tests from real subprocess（子进程） to in-process（进程内） calls.
- [x] 2.2 Reuse existing command runner（命令执行器） or add the smallest helper needed to fake command execution in tests.
- [x] 2.3 Remove or narrow duplicate E2E（端到端测试） coverage that no longer proves a distinct packaged entrypoint behavior.

## 3. Verification

- [x] 3.1 Run the repository-wide test boundary guard.
- [x] 3.2 Capture focused build-and-verify（构建与验证） runtime baseline before refactor and after refactor with the same command: `python -m pytest -q tests/test_build_and_verify_plugin.py`; completion requires both timings to be recorded and no added duplicate E2E（端到端测试） path.
- [x] 3.3 Run repository build-and-verify（构建与验证） fast verification.
- [x] 3.4 Run repository build-and-verify（构建与验证） full verification.
