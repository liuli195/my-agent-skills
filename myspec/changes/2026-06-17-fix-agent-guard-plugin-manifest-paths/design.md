# Design: 修复 agent-guard 插件清单路径前缀

## 修复方案

单一方案：为两份清单的路径字段补 `./` 前缀。

### 现状

```json
{
  "name": "agent-guard",
  "version": "0.1.0",
  "description": "Agent Guard Plugin（代理守卫插件）",
  "hooks": "hooks/hooks.json",
  "skills": "skills",
  "assets": "assets"
}
```

### 修复后

```json
{
  "name": "agent-guard",
  "version": "0.1.0",
  "description": "Agent Guard Plugin（代理守卫插件）",
  "hooks": "./hooks/hooks.json",
  "skills": "./skills",
  "assets": "assets"
}
```

## 关键决策

### 为何不动 `assets`

`assets` 不是 Claude/Codex 清单 schema 认识的字段，两端按"未识别字段"处理（Claude 仅警告、不报错）。当前校验报错只涉及 `hooks` 和 `skills`，`assets` 不在失败项内。本次为最小修复，不顺带改动 `assets`，避免扩大范围。

### 为何两份清单都改

`.claude-plugin/plugin.json` 与 `.codex-plugin/plugin.json` 是同一插件面向两个宿主工具的清单，内容相同、同一根因。Codex 侧虽靠默认目录扫描能跑，但 manifest 字段被解析器忽略属隐患，应一并修正使字段正确生效。

### 路径解析一致性验证

`./hooks/hooks.json` 经 `strip_prefix("./")` 后为 `hooks/hooks.json`，相对插件根解析指向原文件；`./skills` 解析为 `skills/` 目录，与默认扫描目录一致。修复不改变实际加载位置，仅使字段通过校验。

## 测试同步

`tests/test_agent_guard_plugin_package.py` 第 62-63 行断言：

```python
assert codex_manifest["hooks"] == "hooks/hooks.json"
assert claude_manifest["hooks"] == "hooks/hooks.json"
```

更新为：

```python
assert codex_manifest["hooks"] == "./hooks/hooks.json"
assert claude_manifest["hooks"] == "./hooks/hooks.json"
```

`skills` 字段此前无断言，不新增（保持最小修复）。
