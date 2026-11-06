# my-spec

## 概述

一个 Skill（技能），三个命令入口。

| 命令 | 能力 |
|---|---|
| `/spec-audit` | 对照整个仓库审计规格；规格库不存在时创建初始规格 |
| `/spec-review` | 仅审查规格库内部的冲突、重复、过期和格式问题 |
| `/spec-add` | 将 Agent（代理）为当前请求选取的相关证据映射为增量规格并合并 |

`/spec-audit` 将不存在的规格库视为空规格库，因此不再设置独立的 `/spec-init`。

---

# 目标

- 保持 MySpec（自有规格）兼容格式
- 使用 Delta（增量规格）更新主规格
- 自动合并确定重复的规格
- 所有删除逐条确认
- 所有冲突和低可信候选逐条确认
- 应用前展示完整差异并进行最终确认
- 全程严格校验
- 保证相同输入和相同决策不会产生二次变更

---

# 源码与安装结构

## 仓库源码

```text
plugins/my-spec/
├── .claude-plugin/
│   └── plugin.json
├── .codex-plugin/
│   └── plugin.json
├── skills/
│   └── my-spec/
│       ├── SKILL.md
│       ├── references/
│       │   ├── myspec-rules.md
│       │   ├── audit.md
│       │   ├── review.md
│       │   └── add-document.md
│       ├── assets/
│       │   ├── main-spec-template.md
│       │   └── delta-spec-template.md
│       └── scripts/
│           └── spec_ops.py
└── scripts/
    └── install.py
```

## 安装结果

```text
C:\Users\liuli\.agents\skills\my-spec
C:\Users\liuli\.claude\skills\my-spec
    → C:\Users\liuli\.agents\skills\my-spec
```

安装规则：

1. `install.py` 将仓库中的 Skill（技能）复制到 `.agents\skills\my-spec`。
2. Claude（代码代理）目录使用指向该安装目录的目录链接。
3. 重复安装时同步更新 `.agents` 中的安装副本。
4. 如果 Claude 目标路径已存在且不是预期目录链接，安装必须停止。
5. 禁止覆盖或删除来源不明的既有目录。
6. `.agents` 不直接链接仓库源码，源码与安装态保持分离。

---

# 渐进式披露

| 阶段 | 加载内容 |
|---|---|
| Skill（技能）命中 | `SKILL.md` |
| `/spec-audit` | `audit.md` |
| `/spec-review` | `review.md` |
| `/spec-add` | `add-document.md` |
| 修改规格 | `myspec-rules.md` |
| 创建规格 | `assets/*` |
| 校验、预览和应用 | `spec_ops.py` |

---

# 领域模型

## 唯一事实源

```text
myspec/specs/
```

主规格是当前有效行为的唯一事实源。仓库中的文档、测试、代码、注释和示例只作为证据。

## 规格组织

```text
myspec/specs/
└── <capability-name>/
    └── spec.md
```

规则：

- 一个 capability（能力）对应一个 `spec.md`。
- capability（能力）名称使用 `kebab-case`（短横线命名）。
- Requirement（需求）标题在整个规格库中全局唯一。
- Requirement（需求）标题是有语义的身份。
- 不增加无语义 ID（标识符）。

## 标题变化

- 只有输入证据明确声明改名时，才能生成 `RENAMED`（重命名）。
- 没有明确改名证据时，标题变化视为 `REMOVED + ADDED`（删除并新增）。
- 标题不变、正文改变时生成 `MODIFIED`（修改）。
- `MODIFIED` 必须包含完整 Requirement（需求）。

## 可进入规格的内容

只记录可观察、可验证的行为要求：

- 用户或外部系统可触发的行为
- 输入、输出、错误和边界条件
- 权限、安全和兼容性约束
- 可通过 Scenario（场景）验证的规则

以下内容不进入规格：

- 文件结构、类名和函数名
- 内部算法与实现步骤
- 临时计划和待办事项
- 只有实现现状、没有规范意义的代码细节

---

# 三个入口

## `/spec-audit`

对照整个仓库审计主规格。规格库不存在时，将其视为空规格库并创建初始规格。

### 扫描范围

使用以下 Git（版本管理）结果作为仓库文件范围：

```bash
git ls-files --cached --others --exclude-standard
```

排除：

- `myspec/specs/`：作为主规格基准单独读取
- `.local/spec-work/`
- 二进制文件
- 已被 `.gitignore`（忽略规则）排除的依赖和构建产物

### 证据展示优先级

1. 当前主规格
2. 明确的需求、设计和用户文档
3. End-to-End Test（端到端测试）
4. 实现代码
5. 注释、示例和历史文档

优先级只决定展示顺序和推荐答案，不允许自动覆盖主规格。任意来源互相冲突时，必须逐条确认。

### 流程

```text
扫描仓库
→ 读取或建立空主规格基准
→ 提取可验证行为
→ 分类为新增、修改、删除、改名、重复或冲突
→ 生成 Delta（增量规格）
→ 逐条处理冲突和低可信候选
→ 生成完整预览
→ 严格校验
→ 展示完整差异
→ 最终确认
→ 应用
→ 最终校验
```

## `/spec-review`

只读取 `myspec/specs/`，不扫描仓库其他文件。

| 问题 | 处理方式 |
|---|---|
| 标题和正文均相同 | 自动合并 |
| 标题不同但语义等价 | 作为冲突逐条确认 |
| 标题相同但正文不同 | 作为冲突逐条确认 |
| Scenario（场景）部分重叠 | 生成合并建议并逐条确认 |
| 有内部证据证明过期 | 生成删除候选并逐条确认 |
| 无语义影响的格式问题 | 自动修复 |
| 可能改变语义的格式问题 | 作为冲突逐条确认 |

### 过期判定

只有规格库内部存在明确证据时，才生成过期候选：

- 明确声明某 Requirement（需求）已废止
- 明确声明停止支持某 Requirement（需求）
- 新 Requirement（需求）明确声明替代旧 Requirement（需求）
- 版本化 Requirement（需求）明确声明旧版本失效

措辞陈旧、未被其他内容提及、疑似不一致或缺少引用，都不足以证明过期。

## `/spec-add`

```text
Agent（代理）为当前请求选取会话、文档、代码或其他相关证据
→ 读取当前主规格
→ 提取可验证行为
→ 生成相对于主规格的 Delta（增量规格）
→ 完整保存并逐条处理冲突、删除和低可信候选
→ 生成完整预览
→ 严格校验
→ 展示完整差异
→ 最终确认
→ 应用
→ 最终校验
```

指定文档是可选来源。Agent（代理）自主选择当前请求的相关证据，但 `/spec-add` 不执行整个仓库的机械审计。

---

# Agent（代理）与脚本边界

## Agent（代理）负责

- 阅读和理解仓库
- 提取行为要求
- 判断语义重复、冲突和过期候选
- 评估证据可信度
- 生成 Delta（增量规格）
- 给出逐条决策建议

## `spec_ops.py` 负责

- 初始化运行状态和共享锁
- 一次性保存完整 `conflicts` 清单
- 读取当前冲突、记录决定、推进游标和报告状态
- 拒绝只保存数量、越序决定和非法状态转换
- 解析规格
- 校验格式和引用
- 检测确定性重复
- 应用 Delta（增量规格）到预览目录
- 生成完整差异
- 支持原子替换和失败恢复

`spec_ops.py` 不做相似度判断、不调用模型、不推断语义。

---

# 运行时设计

## 工作目录

```text
.local/spec-work/
├── lock
└── current/
    ├── state.json
    ├── delta/
    └── preview/
```

不保留运行历史、持久化审计报告或跨运行拒绝记录。

## 状态

```text
ANALYZING
WAITING_DECISION
READY_TO_APPLY
```

`state.json` 最小结构：

```json
{
  "command": "audit",
  "status": "WAITING_DECISION",
  "specsFingerprint": "<hash>",
  "inputFingerprint": "<hash>",
  "currentConflict": 0,
  "conflicts": [],
  "decisions": []
}
```

恢复运行前重新计算主规格指纹。主规格发生变化时，旧预览和 Delta（增量规格）不得继续应用，必须重新分析。

## 运行锁

- 同一仓库同时只允许一个 my-spec（规格管理）运行。
- `/spec-audit`、`/spec-review` 和 `/spec-add` 共用 `.local/spec-work/lock`。
- 已有锁时停止并报告当前命令和启动时间。
- 异常遗留锁不能只按时间自动删除。
- 只有确认对应进程已不存在后才能清除遗留锁。

---

# 冲突交互

每次只处理一条冲突或低可信候选：

```text
分析完成后一次性保存完整 conflicts
→ 按 currentConflict 读取当前冲突
→ 展示候选内容
→ 展示来源与证据
→ 说明无法自动决定的原因
→ 给出推荐答案
→ 等待用户决定
→ 保存决定
→ 推进游标
→ 从同一 conflicts 清单读取下一项
```

首次展示前必须保存完整清单；只有数量或第一项的状态无效。进入 `WAITING_DECISION` 后禁止重新扫描获取下一项。

用户可以选择：

1. 接受
2. 忽略
3. 修改后接受
4. 暂缓

规则：

- 禁止一次展示全部冲突。
- 禁止“全部采用建议”。
- 删除必须逐条确认。
- 低可信候选视为冲突并逐条确认。
- 暂缓项不进入最终预览。
- 决策只在当前运行内保存。
- 相同输入下次运行时可以再次询问。

---

# 最终应用门禁

所有冲突处理完后：

1. 校验 Delta（增量规格）。
2. 在 `.local/spec-work/current/preview/` 生成完整合并结果。
3. 校验完整预览。
4. 使用 `diff` 输出完整、不截断的文件级差异。
5. 等待用户最终确认。
6. 未确认时不得修改 `myspec/specs/`。
7. 确认后执行目录级替换。
8. 替换后再次校验完整主规格库。

最终门禁展示完整差异，不只展示统计摘要，也不要求展示完整合并后规格正文。

---

# 原子应用与失败恢复

```text
myspec/specs/
    ↓ 重命名
.local/spec-work/current/backup/

.local/spec-work/current/preview/
    ↓ 重命名
myspec/specs/
```

规则：

- 预览和 Delta（增量规格）全部校验通过后才能应用。
- 只替换 `myspec/specs/`。
- 不依赖 Git（版本管理）回滚。
- 不触碰规格目录以外的未提交内容。
- 替换后校验失败时删除错误结果并恢复备份。
- 成功后删除备份、锁和工作区。
- 失败或等待决定时保留工作区。

---

# MySpec（自有规格）规则

第一版不引入外部 MySpec（自有规格）依赖，只实现严格兼容子集。

## Main Spec（主规格）

结构关键字固定为英文，正文语言不限：

```md
# Authentication

## Purpose

描述该能力的目的。

## Requirements

### Requirement: 用户可以使用密码登录

系统 MUST 在凭据有效时允许用户登录。

#### Scenario: 有效凭据

- **WHEN** 用户提交有效凭据
- **THEN** 系统创建登录会话
```

规则：

- `Purpose` 必须存在。
- `Requirements` 必须存在。
- Requirement（需求）标题必须全局唯一。
- 每个 Requirement（需求）必须包含 `MUST` 或 `SHALL`。
- 每个 Requirement（需求）必须至少包含一个 Scenario（场景）。
- 每个 Scenario（场景）必须包含有效的 `WHEN` 和 `THEN`。
- 中文“必须”等词不能替代结构所需的 `MUST` 或 `SHALL`。

## Delta（增量规格）

固定区块：

```md
## ADDED Requirements
## MODIFIED Requirements
## REMOVED Requirements
## RENAMED Requirements
```

应用顺序：

```text
RENAMED → REMOVED → MODIFIED → ADDED
```

校验规则：

- 只允许四类操作。
- 同一 Requirement（需求）不能被多个操作重复处理。
- `REMOVED` 和 `MODIFIED` 引用的标题必须存在。
- `ADDED` 的标题必须不存在。
- `RENAMED` 的旧标题必须存在，新标题必须不存在。
- `MODIFIED` 必须包含完整 Requirement（需求）。

---

# 自动修复边界

可以自动修复：

- 标题层级
- 空行
- 尾随空格
- 文件末尾换行
- Delta（增量规格）区块顺序

不能自动修复：

- 缺失 `MUST` 或 `SHALL`
- 缺失 Scenario（场景）
- 不完整的 `WHEN` 或 `THEN`
- Requirement（需求）标题冲突
- 无法识别的 Requirement（需求）边界
- 任何可能改变语义的问题

不能自动修复的问题必须逐条询问，不得由 Agent（代理）猜写。

---

# `spec_ops.py`

| 命令 | 功能 |
|---|---|
| `state-init <work-dir> <command> <specs-fingerprint> <input-fingerprint>` | 初始化运行状态和共享锁 |
| `state-set-conflicts <work-dir> <conflicts-json> <specs-fingerprint> <input-fingerprint>` | 校验指纹并原子保存完整待决定清单 |
| `state-current <work-dir> <specs-fingerprint> <input-fingerprint>` | 校验指纹并读取当前待决定项 |
| `state-decide <work-dir> <expected-conflict-id> <decision> <specs-fingerprint> <input-fingerprint>` | 校验当前项身份和指纹，保存决定并推进游标 |
| `state-status <work-dir> <specs-fingerprint> <input-fingerprint>` | 校验指纹并报告稳定总数和剩余数 |
| `validate-main <specs-dir>` | 校验完整规格库 |
| `validate-delta <delta-dir> <specs-dir>` | 校验 Delta（增量规格）及其引用 |
| `apply-delta <specs-dir> <delta-dir> <output-dir> <work-dir> <specs-fingerprint> <input-fingerprint>` | 仅在状态就绪且指纹一致时将 Delta（增量规格）应用到预览或主规格 |
| `diff <old-dir> <new-dir>` | 输出完整文件级差异 |

命令约束：

- 成功返回码为 `0`。
- 校验或应用失败返回非 `0`。
- 错误写入标准错误输出。
- 差异写入标准输出。
- 所有路径显式传入。
- 不维护独立 `catalog` 命令；索引由校验和应用过程内部建立。

---

# 幂等规则

- 对文档、主规格和 Delta（增量规格）计算内容指纹。
- 相同输入和相同用户决策必须生成相同预览。
- 已应用的相同 Delta（增量规格）再次运行不得产生二次变更。
- 幂等只约束结果，不保证跨运行不再询问被忽略或暂缓的候选。

---

# 验收

| 场景 | 验收结果 |
|---|---|
| 空规格库运行 `/spec-audit` | 生成初始 Delta（增量规格），最终确认后创建规格库 |
| 已有规格运行 `/spec-audit` | 对照整个仓库生成新增、修改、删除和改名候选 |
| 运行 `/spec-review` | 只读取 `myspec/specs/`，不扫描仓库其他内容 |
| 无指定文档运行 `/spec-add` | 映射 Agent（代理）为当前请求选取的相关证据，不扩展为全仓库审计 |
| 逐项决定被中断后继续 | 从已保存的完整 `conflicts` 清单返回同一当前项，不重新扫描 |
| 标题和正文均相同 | 自动合并 |
| 标题相同但正文不同 | 作为冲突逐条询问 |
| 标题变化但无改名证据 | 作为删除并新增处理 |
| 发现删除候选 | 必须逐条确认 |
| 发现低可信候选 | 作为冲突逐条询问 |
| 最终确认前 | 主规格保持不变 |
| 最终门禁 | 展示完整、不截断的文件级差异 |
| 应用失败 | 完整恢复原主规格 |
| 相同输入和相同决策重复运行 | 不产生二次变更 |
| 重复安装 | 同步更新 `.agents` 安装副本并保持 Claude 目录链接 |
| Claude 目标存在非预期目录 | 安装停止且不覆盖、不删除 |
