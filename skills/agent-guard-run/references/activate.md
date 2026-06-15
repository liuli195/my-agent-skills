# Activate（激活）

激活用于创建或匹配一个 Guard Instance（守卫实例）。

## 入口

项目级 Runtime（运行时）稳定入口：

```text
guard_runner.py activate --profile <id> --scope current_context --source agent-guard-skill --context-json '{"session_id":"..."}'
```

源码仓库辅助脚本：

```powershell
python ../agent-guard/scripts/activate_guard.py
```

## 规则

- 先校验 Guard Profile（守卫画像）存在。
- 校验 `activation.allowed_sources`、`activation.scopes` 和 `activation.required_profile_ref`。
- 按 `subject-resolver.yaml` 读取身份字段；Runtime（运行时）不得自行猜 Subject Key（主体键）。
- 优先匹配已有 Guard Instance（守卫实例）。
- 只有显式 `activate` 可以创建新实例。
- Hook（钩子）事件和 `state_completed` 事件不得创建新实例。
- 缺少必填字段时返回 `no_subject_match` 并写审计。
- 多个候选实例匹配时返回 `ambiguous_subject` 并写审计。

Subject Resolver（主体解析器）通用规则见 `../agent-guard/references/subject-resolution.md`。
