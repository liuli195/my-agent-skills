## Context

`release-flow`（发布流程）的 `preflight`、`publish` 和 `ci-publish` 都通过同一个 `--bump-plugins` 参数接收 `bumpPlugins`（提升插件列表），再调用 `parse_bump_plugins` 校验。

当前参数定义没有 `action`，所以 `argparse` 重复传参时只保留最后一次。后续校验看到部分插件没有声明提升，就报 `plugin_requires_bump`，但根因是 CLI（命令行接口）丢了用户输入。

## Goals / Non-Goals

**Goals:**

- 三个命令入口行为一致。
- 逗号分隔、空字符串、重复传参都被明确测试覆盖。
- 用 Python（编程语言）标准库能力解决。

**Non-Goals:**

- 不新增参数格式。
- 不新增 release-flow（发布流程）配置。
- 不新增依赖或参数解析框架。

## Decisions

1. 使用 `argparse` 的 `append` 收集重复参数。

   这是平台已有能力，能保留所有出现过的值。

2. 扩展 `parse_bump_plugins` 接受字符串或字符串列表。

   单次参数继续按旧逻辑解析；多次参数按逗号分隔后合并。`""` 仍表示不提升插件。

3. 不做去重之外的额外行为。

   重复列出同一个插件不会改变结果，排序保持用户输入顺序。

## Risks / Trade-offs

- 合并重复参数比直接报错更宽容；这是更贴近命令行习惯的最小变更。
- 如果用户同时传 `""` 和非空插件，空值会被当作无内容忽略，非空值仍生效。
