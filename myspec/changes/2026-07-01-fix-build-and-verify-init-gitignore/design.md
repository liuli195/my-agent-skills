## Design

使用固定三行规则作为最小修复：

```gitignore
/cache/
/runs/
/backups/
```

`build-and-verify`（构建与验证）命令行 init（初始化）继续复制模板文件；模板直接包含三行。

`build-and-verify-init`（构建与验证初始化）参考规则改为写入配置前始终保证 `.build-and-verify/.gitignore`（忽略规则）存在并包含三行。已有 `.gitignore`（忽略规则）保留原有内容，只补缺失项。

不新增脚本，不增加配置开关，不改变 runner（运行器）语义。
