# Hook Install（钩子安装）

Hook（钩子）安装默认只做 dry-run（试运行）。只有用户明确授权才写入。

## 安装入口

```powershell
python ../agent-guard/scripts/install_hooks.py --project <target-project> --profile <guard-profile-id>
```

默认输出：

- 将创建或修改的文件。
- Runtime（运行时）调用命令。
- Hook Binding（钩子绑定）摘要。
- 回滚说明。
- 风险提示。

只有显式传入 `--authorize-install` 时才会写入：

- `.agents/guard-runtime/hook_event_adapter.py`
- `.codex/hooks.json`
- `.githooks/pre-push`
- Git 仓库的 `core.hooksPath=.githooks`
- `.agents/guards/<guard-profile-id>/hook-install-plan.md`

Hook（钩子）文件以这些模板为准：

- `../agent-guard/assets/templates/codex-hooks/hooks.json`
- `../agent-guard/assets/templates/git-hooks/pre-push`
- `../agent-guard/assets/templates/guard-runtime/hook_event_adapter.py`

## 验证入口

```powershell
python ../agent-guard/scripts/install_hooks.py --project <target-project> --profile <guard-profile-id> --verify
```

`--authorize-install` 授权安装 Hook（钩子），也授权已安装 Hook（钩子）按 Runtime（运行时）返回的 `deny` 拒绝外部动作。
