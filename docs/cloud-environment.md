# 云端开发环境

一个公共入口负责已发布工具、技能和项目依赖。配置保存在版本库；机器被重建时重新运行入口。MCP 不在本轮范围。

## 使用

需要现成的 Git、Python 3.12、Node/npm。公共入口不安装系统运行时，也不修改登录、凭据或 shell 配置。

```sh
python scripts/cloud_bootstrap.py init --root /workspace/shared/cloud-skills/managed --project .
python scripts/cloud_bootstrap.py update --root /workspace/shared/cloud-skills/managed --project .
python scripts/cloud_bootstrap.py update --root /workspace/shared/cloud-skills/managed --latest --only own-skills
```

第三条仅更新已发布的自有技能；可以用 `--only mattpocock`、`--only find-skills` 或具体 npm 包名选择相应来源。首次使用解析最新正式发布版本，无正式发布渠道的 find-skills 记录具体提交。普通重跑使用已记录版本，清单中的显式版本始终优先，不修改项目锁文件。

声明文件为 `scripts/cloud-environment.json`。给源增加技能路径即可通过同一入口纳管，无需为 data-store 增加专用命令。data-store 尚未出现在正式版本时记录为待发布；未来更新 own-skills 后自动发现。安装范围按顶层目录计算，子技能发现链接不算另一套安装。

`--skills-dir` 可指定已批准的用户技能发现目录。目标存在且不是相同链接时停止，不能覆盖用户安装。安装目录、发现目录和旧环境删除必须先得到具体授权。

公共目录中的 `installed.json` 记录版本，`sources` 使用 Git 稀疏检出，`npm` 使用 npm 正式包；技能发现链接指向唯一运行来源。升级不会自动清理用户目录或旧迁移包。若升级后发现失效技能链接，入口列出路径并停止成功状态，待批准清理后重跑；不会擅自删除用户目录的链接。

## 项目接入

公共清单的 projects 项只登记已支持仓库的既有准备入口、requirements 文件和是否使用 npm。实际包版本仍以目标仓库自己的依赖声明为准，不新增项目配置协议。

- Windows 调用既有 PowerShell 入口，保留其完整默认行为
- Linux 使用公共助手准备 Python/npm，不冒充 Windows 完整工具链
- 链接工作树只能复用与主工作树声明一致且已准备的依赖，不修改主工作树
- Python 主次版本变化需要明确重建环境；Node 版本计入环境身份
- 指纹覆盖嵌套 requirements。pip 按声明满足约束，不承诺删除所有多余包

```sh
python /path/to/my-agent-skills/scripts/cloud_bootstrap.py init --root /workspace/shared/cloud-skills/managed --project /path/to/Quant-Research-Lab
export PATH="$PWD/.venv/bin:/workspace/shared/cloud-skills/managed/npm/bin:$PATH"
build-and-verify verify --project . --execution-context cloud
```

PATH 只影响当前 shell，不写用户配置。公共安装和项目环境版本分别记录。

## Git 工作区生命周期

使用 Git 原生命令，不增加工作区管理工具，也不依赖 Codex 本地环境配置。

1. 核对主工作树、当前变更和已批准的目录；按仓库流程建立功能分支
2. 有隔离需求时，用 git worktree add 创建仓库内工作区；沿用当前工作树的开发流程不额外创建工作区
3. 切换到工作区目录，显式调用上面的统一初始化命令
4. 使用项目解释器和统一构建验证命令开发、验证
5. 按仓库流程交付后，通过 git worktree remove 删除获准清理的工作区，再核对分支和引用

不得强制删除含未交付改动的工作区。外部目录创建、删除仍需明确授权。原有 .worktreeinclude 可保留供其他客户端使用，但本流程不依赖它复制环境。

## 平台范围与验证

公共工具/技能以及三个项目的 Python/npm 准备在云端验证。魔兽仓库的 Windows 游戏工具、原生引擎构建不由本脚本替代；两套引擎身份不变。应继续使用现有本机/CI 流程验证这些能力。

测试由现有 build-and-verify 配置纳管。日常测试不联网下载；实际安装只在批准位置做入口冒烟。本机沿用既有预算，云端不继承本机总截止。
