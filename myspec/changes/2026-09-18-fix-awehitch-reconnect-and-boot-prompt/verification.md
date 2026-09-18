# 验证证据

本文件按实施规程保留可复核的原始证据（已脱敏：不含任何凭据）。

固定基线：`9fc5145bb68506c32d5cd4d9f0e30bacd6177fec`
工作树：`D:/My Project/my-agent-skills`　分支：`claude/awehitch-codex-config-fix`

## 一、正式验证

```
build-and-verify verify --project . --base 9fc5145bb68506c32d5cd4d9f0e30bacd6177fec
```

- `status: passed`
- `checked`（非空，8 项）：`verify.local-build-contract`、`verify.release-flow`、`verify.pr-flow`、
  `verify.myspec`、`verify.my-spec`、`verify.runtime-boundaries`、`verify.build-and-verify`、
  `verify.build-and-verify-cli`

**首轮曾失败，已定位并排除**：`verify.release-flow` / `verify.pr-flow` 报 23 项失败，
根因是 `%TEMP%` 下**残留的模板缓存目录里含只读 git object 文件**，Windows 上
`shutil.rmtree` 删不掉（`PermissionError: [WinError 5]`）。**已在基线提交上跑同一套对照，
得到完全相同的 23 项失败**，确认与本次改动无关；清掉那两个具名目录后转绿。

## 二、最终真实入口冒烟

入口：Agent（代理）照技能真连一次 —— 开对话 → 发引导词 → 收回复。

**发送**（`awehitch_send_state`，任务标识 `smoke-boot-prompt-compressed`）：

```json
{"ok": true, "sent": true, "url": "https://chatgpt.com/c/6aad3893-5ffc-83ee-b16c-219dbd13a318"}
```

发送内容即压缩后的引导词：**816 字节、以 `[C2C]` + `STATE: BOOT` 开头**。
（改前为 1361 字节、无前缀，被发送通道硬性拒收 —— 这正是本次要修的缺陷。）

**ChatGPT 的回复**（`awehitch_wait_reply`，原样）：

```
[C2C]
STATE: PLAN

Workspace: my-agent-skills
Branch: claude/awehitch-codex-config-fix
HEAD: 7f89fec2
Git: clean; ahead of upstream by 4 commits; no staged/unstaged/untracked changes; current HEAD diff is empty.

Planning/review layer initialized. Send the task, HANDOFF, or EXECUTED message.
```

**这证明了三件事**：
1. 改前**永远发不出去**的引导词，现在发送通道接受了
2. ChatGPT 按引导词设定的角色工作（"Planning/review layer initialized"）
3. 它**真的通过只读连接器读了本工作区** —— 报出的工作区名、分支、`HEAD: 7f89fec2`
   与本地一致，并按 C2C 格式回话

## 三、补丁重放验证

- 从 `.orig`（上游原始模板）还原后重跑补丁脚本，补丁 2 / 6 / 7 均**可干净重放**
- 幂等：连续重跑报告全部「已打 → 跳过」、重渲染「与模板一致 → 跳过」，无多余写入
- 被改文件行尾保持全 LF（补丁 5 的 `runtime.js` 实测 `CRLF=0`）
- `node --check` 通过（`runtime.js`、`codex.js`、`cli/index.js`）

## 四、本轮审查发现并修复的问题

两轴独立审查（标准 / 规格，均为只读子代理）共提出 11 项，其中**阻塞项 6 项已全部修复**：

| 问题 | 处置 |
|---|---|
| 重连节写成了票 02 明令禁止的笼统说法 | 改写为准确表述；加测试钉住禁止的说法不许回归 |
| 5 个送出的文本块只护住 3 个（INIT／EXECUTED 无保护） | 测试扩到全部 5 块 |
| 重渲染裸读模板，缺文件时整脚本抛错 | 加存在性保护 |
| **补丁判不准时重渲染仍会用未打补丁的模板覆盖本机技能**（静默降级） | 加 `$tplUncertain` 闸门，判不准即停手 |
| 补丁 7 未建 `.orig` | 统一到 `$tpl`，`.orig` 由首个模板补丁建立并复用 |
| **补丁 2 的自检假阳性导致它永不重打**（见下） | 删除该启发式 |

**补丁 2 的假阳性是本轮最严重的一处**：它拿 `connectorName` 当「上游已处理」的特征，而
**上游自己的文字里就有这个词** → 对未打补丁的原始模板也命中 → 补丁 2 被判「上游已处理」
而永不重打，`npm update` 之后那段说明会**永久丢失**。这个问题在从 `.orig` 还原后重跑时
当场暴露，现已删除该猜测。

未阻塞的判断题（命名、重复代码、规格外改动）已记录，留待门禁二一并决定。

## 五、修复阻塞项后的重跑（最终状态）

修复后 `HEAD` = `a0a917ed`，`build-and-verify` 重跑：`status: passed`（209 passed，较修复前多 1
项＝新增的那条测试）。

**重跑真实入口冒烟**（任务标识 `smoke-after-review-fixes`）：

发送：`{"ok": true, "sent": true, "url": "https://chatgpt.com/c/6aad3ae2-2acc-83ee-9846-be4aad8115a5"}`

回复（原样）：

```
[C2C]
STATE: PLAN

WORKSPACE: my-agent-skills
BRANCH: claude/awehitch-codex-config-fix
HEAD: a0a917ed

Git（版本管理）状态：
工作区干净 / staged 0 / unstaged 0 / untracked 0 / conflicted 0
当前分支相对 upstream：ahead 5 / behind 0
HEAD diff（当前提交差异）：空

已读取工作区顶层结构、AGENTS.md 和 CONTEXT.md，后续会按任务重新读取相关源码并基于真实 Git diff（差异）进行验证。

NEXT_EXPECTED_STEP: 发送具体 TASK / HANDOFF。
```

报出的 `HEAD` 与本地一致，且它按引导词设定的角色与格式回话 —— 修复后仍然成立。

## 六、完成检查（实施阶段收尾）

```
git diff --name-only 9fc5145b -- myspec/specs/            → 空
git ls-files --others --exclude-standard -- myspec/specs/ → 空
```

两条均为空：实施全程**未触碰 `myspec/specs/`**，无提前写入的正式规格。

