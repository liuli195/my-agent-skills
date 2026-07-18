## 1. Runner Configuration

- [x] 1.1 Update config validation to reject old `parallel` and accept `checkParallel`.
- [x] 1.2 Add `pytestXdistWorkers` validation and pytest command application.
- [x] 1.3 Reuse one check scheduler for fast and full verification.

## 2. Initialization

- [x] 2.1 Extend `init` with `--config` and `--overwrite`.
- [x] 2.2 Add backup, `.gitignore` merge, runtime copy, and cache creation to overwrite init.
- [x] 2.3 Update `build-and-verify-init` references to call `init --config --overwrite`.
- [x] 2.4 Update dependency checks so drafts with `pytestXdistWorkers` check for `pytest-xdist`, report impact and advice, and still allow user-confirmed writes without auto-installing dependencies.

## 3. Current Repository Configuration

- [x] 3.1 Replace only `D:\My Project\my-agent-skills` repository `parallel` fields with `checkParallel`.
- [x] 3.2 Refresh only `D:\My Project\my-agent-skills` repository runtime snapshot.
- [x] 3.3 Do not initialize, overwrite, or mutate `D:\My Project\Quant-Research-Lab` in this workflow.

## 4. Verification

- [x] 4.1 Add focused regression tests for init, `checkParallel`, fast scheduling, and `pytestXdistWorkers`.
- [x] 4.2 Run build-and-verify plugin tests.
- [x] 4.3 Run OpenSpec strict validation.
- [x] 4.4 Run an end-to-end initialization regression against a temporary target repository: confirm config write through `init --config --overwrite`, runtime copy, cache creation, optional backup behavior, and no mutation of external user repositories.
- [x] 4.5 Run repository fast verification.
- [x] 4.6 Run repository full verification.
