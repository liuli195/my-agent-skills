你现在负责在当前计算机的当前用户账户中，完整安装并配置：

- pi-memory（Pi 本地长期记忆扩展）
- QMD（本地文档检索引擎）
- Qwen3-Embedding-0.6B（通义千问中文语义嵌入模型）
- Transition Summary（会话转换摘要）

不要只输出教程或命令，必须直接使用可用的 Shell（命令行）、文件读写和编辑工具执行。

除非遇到本提示词明确规定的阻塞条件，否则不要询问确认。遇到阻塞条件时，不要绕过安全要求；停止受影响的后续步骤，保留已安全完成的结果，并输出清晰报告。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
一、安装范围与最终目标
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

最终目标：

1. 将 pi-memory 作为 Global Package（全局包）安装。
2. 通过 npm（Node.js 包管理器）全局安装 QMD。
3. 建立名为 `pi-memory` 的 QMD Collection（检索集合）。
4. 中文语义检索使用 Qwen3-Embedding-0.6B。
5. 确保 `PI_MEMORY_SNAPSHOT=stable`。
6. 确保 `PI_MEMORY_QMD_UPDATE=background`。
7. 明确不启用 `PI_MEMORY_SNAPSHOT=per-turn`。
8. 启用 `PI_MEMORY_SUMMARIZE_TRANSITIONS=1`。
9. 不启动 QMD MCP Server（QMD 模型上下文协议服务器）。
10. 不新增或修改任何 MCP（模型上下文协议）客户端配置。
11. 不创建、不修改 `<HOME>/.pi/agent/AGENTS.md`。
12. 不创建、不修改任何 Skill（技能）或 `SKILL.md`。
13. 不主动写入测试性长期记忆、Daily Log（每日日志）或 Scratchpad（临时清单）。
14. 所有操作必须幂等：重复执行不得产生重复配置、重复 Context（路径说明）或重复环境变量块。
15. 不删除任何现有记忆、QMD Collection、QMD 文档、MCP 配置或其他用户配置。
16. 修改现有文件、环境变量或 Shell Profile（命令行配置文件）前，必须创建带时间戳的备份或在报告中记录原值。
17. 不在输出、日志或配置中写入密码、API Key（接口密钥）、Access Token（访问令牌）、Cookie（浏览器凭据）或私钥。
18. 不使用 Git 开发分支、未发布提交或来源不明的包。
19. 不擅自设置 `PI_MEMORY_DIR`，使用 pi-memory 默认记忆目录。
20. 不擅自启用 `deep`（深度检索）测试，不预下载 Query Expansion（查询扩展）或 Reranker（重排序）模型。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
二、环境预检
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

先检测并记录以下信息：

- 操作系统及版本
- CPU 架构
- 当前 Shell（命令行）
- 当前用户
- HOME 或 USERPROFILE 的绝对路径
- `node --version`
- `npm --version`
- `npm prefix -g`
- `pi --version`
- `pi list`
- `pi install --help`
- `qmd` 是否已经存在
- `qmd --version`，仅在 qmd 已存在时运行
- `QMD_CONFIG_DIR`
- `XDG_CONFIG_HOME`
- `XDG_CACHE_HOME`
- `PI_MEMORY_DIR`
- `PI_MEMORY_SNAPSHOT`
- `PI_MEMORY_QMD_UPDATE`
- `PI_MEMORY_SUMMARIZE_TRANSITIONS`
- `PI_MEMORY_NO_SEARCH`

Windows 还要分别检查以下作用域中的环境变量：

- Process（当前进程）
- User（当前用户）
- Machine（系统级）

至少检查：

- `PI_MEMORY_SNAPSHOT`
- `PI_MEMORY_QMD_UPDATE`
- `PI_MEMORY_SUMMARIZE_TRANSITIONS`
- `QMD_CONFIG_DIR`

要求：

1. 查询实际包要求：

   npm view pi-memory name version repository.url homepage
   npm view @tobilu/qmd name version repository.url homepage engines

2. Node.js 的主版本必须：

   - 不低于 22；
   - 同时满足 `@tobilu/qmd` 当前 npm 包的 `engines` 要求。

3. 如果当前 Node.js 不满足要求：

   - 优先检测现有的 fnm、mise、volta、nvm、nvm-windows 或其他 Node.js 版本管理器。
   - 如果已有版本管理器，使用它安装并激活“满足 QMD engines 要求的最新 LTS（长期支持）版本”，然后重新验证 Node.js 和 npm。
   - 不要擅自卸载系统 Node.js。
   - 不要覆盖用户现有的版本管理器配置。
   - 如果没有可用的版本管理器，停止后续安装并报告：
     - 当前 Node.js 版本；
     - QMD 实际要求；
     - 为什么当前环境不满足；
     - 当前操作系统适用的最小升级方案。

4. 如果找不到 `pi` 命令：

   - 立即停止后续安装；
   - 不要擅自安装或重新安装 Pi；
   - 报告 PATH（环境变量路径）和检测结果。

5. 检查 `pi list`。

   如果发现 pi-memory 之外的扩展会执行以下任一行为：

   - 提供长期记忆；
   - 自动注入长期上下文；
   - 注册同名或相近的 `memory_*` 工具；
   - 接管 Session Compaction（会话压缩）或 Session Handoff（会话交接）；
   - 自动总结并写入长期记忆；

   则：

   - 不要卸载该扩展；
   - 不要安装 pi-memory；
   - 列出扩展名称；
   - 说明可能发生的工具重名、重复写入、上下文重复注入或数据不一致；
   - 停止 pi-memory 安装步骤。

   不要把普通文档检索、代码搜索或无关扩展误判为记忆扩展。

6. 核对 npm 包来源。

   将 npm 返回的仓库地址标准化后，必须分别对应：

   - `jayzeng/pi-memory`
   - `tobi/qmd`

   允许 `https://github.com/...`、`git+https://github.com/...` 或带 `.git` 后缀的等价官方地址。

   如果来源不符或无法确认，立即停止，不安装该包。

7. 检查现有的 `PI_MEMORY_DIR`。

   - 如果未设置，继续使用默认目录。
   - 如果已经设置，记录其来源和绝对路径。
   - 不要擅自删除或覆盖该设置。
   - 后续记忆目录应使用 pi-memory 实际有效目录，而不是强行使用默认目录。
   - 如果 Process、User、Machine 或 Shell Profile 中存在相互冲突的 `PI_MEMORY_DIR`，停止并报告。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
三、安装 pi-memory 和 QMD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 根据 `pi install --help` 确认 Global Package（全局包）的实际安装语法。

2. 检查 `pi list` 是否已经包含 `npm:pi-memory` 或等价的全局 pi-memory 安装项。

3. 如果尚未安装：

   - 使用 Pi 当前版本支持的全局安装方式安装；
   - 优先使用：

     pi install npm:pi-memory

   - 不创建项目级安装；
   - 不使用本地 Git Checkout（检出目录）；
   - 不使用 Git 开发分支。

4. 如果 pi-memory 已安装：

   - 不重复添加安装记录；
   - 确认其来源是 npm 官方包；
   - 记录当前已安装版本；
   - 使用 `npm view pi-memory version` 检查最新稳定版本；
   - 只有在 Pi 当前 CLI 明确提供官方更新命令时，才可使用该命令更新；
   - 更新前先查看对应 `--help`；
   - 不猜测不存在的更新命令；
   - 如果无法安全确定更新方法，保留当前版本，并在报告中注明是否存在可用更新。

5. 安装或更新 QMD：

   npm install -g @tobilu/qmd

6. 验证：

   pi list
   qmd --version
   qmd --help
   qmd doctor

7. 确认当前 Shell 可以直接解析 qmd：

   - Windows PowerShell（Windows 命令行）使用：

     Get-Command qmd -ErrorAction Stop

   - Linux/macOS 使用：

     command -v qmd

8. 如果 npm 安装成功但 qmd 不在 PATH：

   - 获取 `npm prefix -g`；
   - 确认实际全局可执行目录；
   - 只修改当前用户的 PATH；
   - 不修改 Machine（系统级）PATH；
   - 修改前记录完整原值；
   - 修改 Shell Profile 前创建带时间戳的备份；
   - 使用带 BEGIN/END 标记的幂等配置块；
   - 修改后在当前进程中临时补充 PATH；
   - 重新验证：

     qmd --version
     qmd doctor

9. 如果 QMD 仍无法运行：

   - 保留完整错误摘要；
   - 不继续创建 Collection；
   - 不继续修改 QMD 配置文件；
   - 最终状态标记为 FAIL。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
四、确定记忆目录与 QMD 配置目录
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 确定 pi-memory 实际有效的 Memory Directory（记忆目录）。

   优先级：

   - 如果有效设置了 `PI_MEMORY_DIR`，使用其展开后的绝对路径；
   - 否则使用：

     <HOME>/.pi/agent/memory

2. 不依赖 Shell 是否会展开 `~`，所有命令都使用绝对路径。

3. 创建以下目录，但不得清空、覆盖或重建已有内容：

   <Memory Directory>
   <Memory Directory>/daily
   <Memory Directory>/recovery

4. 不手动创建或改写以下文件：

   - `MEMORY.md`
   - `SCRATCHPAD.md`
   - 已有 Daily Log（每日日志）
   - 已有 Recovery Record（恢复记录）

   这些内容由 pi-memory 管理。

5. 确定 QMD Config Directory（QMD 配置目录），优先级为：

   - 如果设置了 `QMD_CONFIG_DIR`，使用该目录；
   - 否则，如果设置了 `XDG_CONFIG_HOME`，使用：

     <XDG_CONFIG_HOME>/qmd

   - 否则使用：

     <HOME>/.config/qmd

6. QMD 主配置文件应为：

   <QMD Config Directory>/index.yml

7. 记录 QMD Cache/Index Directory（缓存或索引目录）。

   - 优先通过 `qmd status`、`qmd doctor` 或 QMD 当前版本帮助信息确定；
   - 不凭经验猜测；
   - 如果命令没有显示，报告为“未由当前 QMD 版本公开”。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
五、创建或验证 pi-memory Collection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 先查看当前 QMD 命令语法：

   qmd collection --help
   qmd context --help

2. 运行：

   qmd collection list

3. 检查是否已经存在名为 `pi-memory` 的 Collection（集合）。

4. 如果不存在，使用当前 QMD 版本支持的等价命令创建：

   qmd collection add "<Memory Directory 的绝对路径>" --name pi-memory

5. 如果已经存在：

   - 使用：

     qmd collection show pi-memory

   - 检查其 path 是否与实际 Memory Directory 完全一致；
   - 解析路径大小写、目录分隔符和符号链接后再比较；
   - 如果路径一致，保留；
   - 如果路径不一致：
     - 不删除 Collection；
     - 不覆盖 Collection；
     - 停止后续索引和模型配置；
     - 最终状态标记为 FAIL；
     - 报告现有路径和目标路径。

6. 检查现有 Context（路径说明）：

   qmd context list

7. 确保 `pi-memory` Collection 中存在以下 Context，且不得重复：

   路径：

   /daily

   内容：

   Daily append-only work logs organized by date（按日期组织的每日追加工作日志）

   路径：

   /

   内容：

   Curated long-term memory: decisions, preferences, facts, corrections and lessons（精选长期记忆：决策、偏好、事实、纠正和经验）

8. 如果 Context 不存在，使用当前 QMD 版本支持的等价命令添加：

   qmd context add /daily "Daily append-only work logs organized by date（按日期组织的每日追加工作日志）" -c pi-memory

   qmd context add / "Curated long-term memory: decisions, preferences, facts, corrections and lessons（精选长期记忆：决策、偏好、事实、纠正和经验）" -c pi-memory

9. 如果相同路径已经存在但内容不同：

   - 不创建第二份重复 Context；
   - 优先使用当前 QMD CLI 提供的 update/set 命令；
   - 如果当前 CLI 没有更新命令，再在完成配置文件备份后，以结构化 YAML 方式更新；
   - 不使用可能破坏 YAML 的简单全文替换；
   - 不删除其他 Collection 或 Context。

10. 验证：

    qmd collection show pi-memory
    qmd context list

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
六、配置 Qwen3-Embedding-0.6B
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

目标 Embedding Model（嵌入模型）：

hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf

1. 确认 `<QMD Config Directory>/index.yml` 已存在。

2. 如果配置文件尚不存在：

   - 先重新运行：

     qmd collection show pi-memory
     qmd collection list

   - 如果 QMD 当前版本提供初始化命令，则先查看帮助后使用；
   - 不创建与当前 QMD 配置格式不兼容的猜测性文件。

3. 如果配置文件存在，修改前创建完整时间戳备份：

   index.yml.backup-YYYYMMDD-HHMMSS

4. 读取整个 YAML，必须保留：

   - 所有现有 collections；
   - 所有 Collection path；
   - 所有 pattern；
   - 所有 ignore；
   - 所有 update command；
   - 所有 context；
   - `global_context`；
   - `editor_uri`；
   - `models.rerank`；
   - `models.generate`；
   - `includeByDefault`；
   - 其他未知或未来版本字段。

5. 不使用简单正则表达式整体重写 YAML。

   优先使用：

   - YAML Parser（YAML 解析器）；
   - 或精确、结构感知的编辑方式。

6. 先确认当前 QMD 版本是否支持 Per-Collection Embedding Model（按集合指定嵌入模型）：

   - 查看 `qmd --help`；
   - 查看 `qmd collection --help`；
   - 查看当前生成的 `index.yml` 结构；
   - 查看本地已安装包附带的 README 或配置示例。

7. 如果当前 QMD 版本支持按 Collection 指定 Embedding Model：

   - 仅为 `pi-memory` Collection 配置目标 Qwen3 模型；
   - 不改变其他 Collection 的模型。

8. 如果当前 QMD 版本只支持全局 `models.embed`：

   先运行：

   qmd collection list
   qmd status

   然后按以下规则处理：

   A. 仅存在 `pi-memory` Collection：

   - 在 YAML 顶层添加或更新：

     models:
       embed: "hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf"

   B. 存在其他 Collection，但当前全局模型已经是相同的 Qwen3 模型：

   - 保留该模型；
   - 不重复修改。

   C. 存在其他 Collection，且当前全局模型不是目标 Qwen3 模型或未明确配置：

   - 不擅自迁移其他 Collection；
   - 不擅自强制重建其他 Collection 的向量；
   - 保留现有模型设置；
   - 继续保留已经完成的 pi-memory 和 QMD 安装；
   - 不声称中文模型已经配置成功；
   - 在最终报告中标记：

     CHINESE_MODEL_MIGRATION_SKIPPED

   - 最终整体状态不得标记为 PASS，只能标记为 PARTIAL；
   - 说明原因：当前 QMD 模型为全局配置，更换模型会影响其他 Collection。

9. 如果 `models` 已存在：

   - 只更新 `models.embed`；
   - 不删除或覆盖 `models.rerank`；
   - 不删除或覆盖 `models.generate`；
   - 不删除其他模型字段。

10. 修改后重新读取并验证：

    - YAML 可正常解析；
    - 缩进有效；
    - 所有原有 Collection 仍存在；
    - `pi-memory` Collection 路径正确；
    - Context 没有丢失；
    - 目标场景下 `models.embed` 值正确；
    - 未发生未知字段丢失。

11. 如果 YAML 验证失败：

    - 立即恢复最近的备份；
    - 不继续执行 `qmd update` 或 `qmd embed`；
    - 状态标记为 FAIL。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
七、建立索引和 Embedding（嵌入向量）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 执行：

   qmd update

2. 根据模型配置状态执行：

   A. 本次刚把模型切换为 Qwen3：

   qmd embed -f

   B. 当前原本已经使用同一个 Qwen3 模型：

   qmd embed

   C. 因其他 Collection 冲突而跳过 Qwen3 迁移：

   qmd embed

3. 第一次运行可能下载模型。

   - 必须等待命令实际完成；
   - 不要在下载、校验或生成向量过程中提前宣称成功；
   - 保留关键进度和最终退出状态；
   - 不在报告中粘贴无关的大量下载日志。

4. 如果 GPU Backend（图形处理器后端）失败：

   - 保留原始错误摘要；
   - 只使用临时环境变量 `QMD_FORCE_CPU=1` 重试一次；
   - 不立即永久禁用 GPU。

   Windows PowerShell：

   $env:QMD_FORCE_CPU = "1"
   qmd embed -f

   Linux/macOS：

   QMD_FORCE_CPU=1 qmd embed -f

   根据前面实际应执行的是 `qmd embed` 还是 `qmd embed -f`，保持对应参数一致。

5. 如果 GPU 失败但 CPU 成功：

   - 将“发生 CPU 回退”记录为 Yes；
   - 不永久设置 `QMD_FORCE_CPU`；
   - 不修改用户级 GPU 配置。

6. 如果 GPU 和 CPU 均失败：

   - 状态标记为 FAIL；
   - 保留错误摘要；
   - 不尝试安装来源不明的 GPU Runtime（运行时）、驱动或二进制文件。

7. 不运行：

   - `deep` 模式；
   - Query Expansion（查询扩展）；
   - Reranker（重排序）测试；
   - QMD MCP Server；
   - 任何会启动长期后台服务的 QMD 命令。

8. 不主动创建测试记忆文件。

9. 如果记忆目录当前没有可索引的 Markdown 文档：

   - 不把零文档视为安装失败；
   - 报告状态为 `READY_NO_DOCUMENTS`；
   - 仍需验证 Collection、模型配置和 QMD 健康状态；
   - 不为测试而污染长期记忆目录。

10. 执行最终 QMD 检查：

    qmd doctor
    qmd status
    qmd collection show pi-memory
    qmd context list

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
八、配置 pi-memory Runtime（运行参数）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

需要确保以下最终有效值：

- `PI_MEMORY_SNAPSHOT=stable`
- `PI_MEMORY_QMD_UPDATE=background`
- `PI_MEMORY_SUMMARIZE_TRANSITIONS=1`

明确禁止：

- `PI_MEMORY_SNAPSHOT=per-turn`
- `PI_MEMORY_QMD_UPDATE=manual`
- `PI_MEMORY_QMD_UPDATE=off`

说明：

- `stable` 用于保持 KV Cache（键值缓存）稳定。
- `background` 用于在记忆写入后后台更新 QMD 索引和 Embedding。
- `PI_MEMORY_SUMMARIZE_TRANSITIONS=1` 用于启用 Transition Summary（会话转换摘要）。
- 不配置或启动 QMD MCP Server。

配置必须对当前用户后续启动的新 Pi 进程生效。

### Windows

1. 读取并记录以下环境变量的原始 User（当前用户）值：

   - `PI_MEMORY_SNAPSHOT`
   - `PI_MEMORY_QMD_UPDATE`
   - `PI_MEMORY_SUMMARIZE_TRANSITIONS`

2. 不修改 Machine（系统级）环境变量。

3. 设置 User（当前用户）环境变量：

   [Environment]::SetEnvironmentVariable(
     "PI_MEMORY_SNAPSHOT",
     "stable",
     "User"
   )

   [Environment]::SetEnvironmentVariable(
     "PI_MEMORY_QMD_UPDATE",
     "background",
     "User"
   )

   [Environment]::SetEnvironmentVariable(
     "PI_MEMORY_SUMMARIZE_TRANSITIONS",
     "1",
     "User"
   )

4. 同时设置当前 PowerShell 进程，便于本次验证：

   $env:PI_MEMORY_SNAPSHOT = "stable"
   $env:PI_MEMORY_QMD_UPDATE = "background"
   $env:PI_MEMORY_SUMMARIZE_TRANSITIONS = "1"

5. 重新读取 User 和 Process 作用域并验证。

6. 如果 Machine 作用域中存在冲突值：

   - 不修改 Machine 作用域；
   - 记录冲突；
   - 验证 User 和新 Process 是否能覆盖；
   - 如果不能确认最终 Pi 进程将获得正确值，状态标记为 PARTIAL。

### Linux/macOS：Bash 或 Zsh

1. 根据当前登录 Shell 选择实际启动文件：

   - Zsh：优先使用 `~/.zshrc`
   - Bash：优先使用 `~/.bashrc`
   - 如果当前环境明确只加载 `~/.bash_profile` 或 `~/.profile`，使用实际生效文件

2. 修改前创建完整时间戳备份。

3. 使用以下唯一标记块，确保幂等：

   # BEGIN PI_MEMORY_RUNTIME
   export PI_MEMORY_SNAPSHOT="stable"
   export PI_MEMORY_QMD_UPDATE="background"
   export PI_MEMORY_SUMMARIZE_TRANSITIONS="1"
   # END PI_MEMORY_RUNTIME

4. 如果标记块不存在，追加到文件末尾。

5. 如果标记块已存在，完整替换该块。

6. 不修改标记块以外内容。

7. 在当前进程中执行等价的 export，以便本次验证。

### Linux/macOS：Fish

1. 使用 Fish 的用户级 Universal Variable（通用变量），或修改实际生效的 Fish 配置文件。

2. 如果使用配置文件，修改前创建时间戳备份，并使用唯一标记块。

3. 最终确保：

   set -Ux PI_MEMORY_SNAPSHOT stable
   set -Ux PI_MEMORY_QMD_UPDATE background
   set -Ux PI_MEMORY_SUMMARIZE_TRANSITIONS 1

4. 不创建重复配置。

### 其他 Shell

1. 不猜测配置方式。
2. 检查该 Shell 的用户级持久环境变量方法。
3. 修改任何配置文件前创建备份。
4. 如果无法可靠持久化，设置当前进程值，并将整体状态标记为 PARTIAL。

### Runtime（运行参数）验证

验证当前进程中的值：

- `PI_MEMORY_SNAPSHOT` 必须为 `stable`
- `PI_MEMORY_QMD_UPDATE` 必须为 `background`
- `PI_MEMORY_SUMMARIZE_TRANSITIONS` 必须为 `1`

还要确认：

- 没有把 `PI_MEMORY_SNAPSHOT` 设置为 `per-turn`
- 没有设置 `PI_MEMORY_QMD_UPDATE=manual`
- 没有设置 `PI_MEMORY_QMD_UPDATE=off`
- 没有永久设置 `QMD_FORCE_CPU`
- 没有启动 QMD MCP Server
- 没有修改任何 MCP 客户端配置

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
九、明确排除 AGENTS.md 和 Skill
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

本次安装不得执行以下操作：

1. 不创建或修改：

   <HOME>/.pi/agent/AGENTS.md

2. 不创建或修改项目级 `AGENTS.md`。

3. 不创建或修改：

   <HOME>/.pi/agent/skills/

4. 不创建或修改任何 `SKILL.md`。

5. 不添加以下类型的行为规则：

   - 主动记忆写入规则；
   - Recall Policy（召回策略）；
   - 去重规则；
   - Memory Safety Policy（记忆安全策略）；
   - 任务结束自动检查规则。

6. 如果安装开始前 `AGENTS.md` 已存在：

   - 只记录其存在；
   - 不读取无关内容；
   - 不修改；
   - 不备份，因为本次不应触碰该文件。

7. 最终报告必须明确写明：

   AGENTS_MD_MODIFIED: No
   SKILLS_MODIFIED: No

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
十、最终验证
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

执行并保存结果：

- `node --version`
- `npm --version`
- `npm prefix -g`
- `pi --version`
- `pi list`
- `qmd --version`
- `qmd doctor`
- `qmd status`
- `qmd collection show pi-memory`
- `qmd context list`

再次验证：

1. pi-memory 已出现在 Global Package（全局包）列表中。
2. pi-memory 来源为官方 npm 包。
3. QMD 来源为官方 npm 包。
4. qmd 命令可直接运行。
5. pi-memory Collection 路径正确。
6. `/daily` Context 存在且不重复。
7. `/` Context 存在且不重复。
8. QMD 配置文件可以正常解析。
9. Qwen3-Embedding-0.6B 已正确配置；如果因现有其他 Collection 冲突而跳过，必须标记 PARTIAL。
10. Embedding 状态正常，或在零文档情况下显示 `READY_NO_DOCUMENTS`。
11. `PI_MEMORY_SNAPSHOT=stable`。
12. `PI_MEMORY_QMD_UPDATE=background`。
13. `PI_MEMORY_SUMMARIZE_TRANSITIONS=1`。
14. 没有启用 `per-turn`。
15. 没有永久设置 `QMD_FORCE_CPU`。
16. 没有启动 QMD MCP Server。
17. 没有新增或修改 MCP 客户端配置。
18. 没有创建或修改 `AGENTS.md`。
19. 没有创建或修改 Skill（技能）。
20. 没有删除已有记忆、Collection 或用户配置。
21. 没有向长期记忆目录写入测试内容。

注意：

- 当前 Pi 进程如果是在安装前启动的，可能尚未加载新扩展或新环境变量。
- 在这种情况下，不要声称 `memory_status` 已经可用。
- 不要为了验证 Transition Summary 而擅自执行 `/new`、`/fork` 或额外 `/reload`。
- 本阶段只验证 Transition Summary 的持久环境变量已经配置。
- Transition Summary 的运行时生效状态应在用户执行 `/reload` 后通过 pi-memory 状态检查确认。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
十一、生成安装报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

将最终报告写入：

<HOME>/.pi/agent/pi-memory-setup-report.md

如果 `<HOME>/.pi/agent` 不存在，可以创建目录，但不得创建或修改 `AGENTS.md`。

报告必须包含：

# pi-memory + QMD Setup Report

## Overall Status（总体状态）

只能使用：

- PASS
- PARTIAL
- FAIL

### PASS 条件

只有同时满足以下条件才能标记 PASS：

- pi-memory 安装成功；
- QMD 安装成功；
- Collection 路径正确；
- Context 正确；
- Qwen3 模型配置成功；
- QMD 索引或零文档就绪状态正常；
- Runtime 环境变量正确；
- Transition Summary 已配置为启用；
- 没有启用 per-turn；
- 没有启动 MCP Server；
- 没有修改 AGENTS.md 或 Skill。

### PARTIAL 条件

包括但不限于：

- 因其他 QMD Collection 使用不同模型而跳过 Qwen3 迁移；
- 环境变量只在当前进程生效，无法可靠持久化；
- pi-memory 已安装但无法安全确定更新方式；
- GPU 失败但 CPU 成功不属于 PARTIAL，只需记录 CPU 回退；
- 当前没有文档导致无法验证实际语义召回，但模型和索引配置正常时可保持 PASS，并标记 `READY_NO_DOCUMENTS`。

### FAIL 条件

包括但不限于：

- Pi 不存在；
- Node.js 不满足要求且无法安全升级；
- npm 包来源不可信；
- 发现冲突记忆扩展；
- QMD 无法运行；
- Collection 路径冲突；
- YAML 修改失败且无法恢复；
- GPU 和 CPU Embedding 均失败；
- pi-memory 安装失败。

报告字段至少包括：

- Overall Status（总体状态）
- 操作系统
- CPU 架构
- 当前 Shell
- HOME 绝对路径
- Node.js 版本
- npm 版本
- Pi 版本
- pi-memory 已安装版本
- pi-memory 最新稳定版本
- QMD 已安装版本
- QMD 最新稳定版本
- Memory Directory（记忆目录）
- QMD Config Directory（QMD 配置目录）
- QMD Config File（QMD 配置文件）
- QMD Cache/Index Directory（QMD 缓存或索引目录）
- QMD Collection 状态
- Collection 文档数量
- Context 状态
- 当前 Embedding Model（嵌入模型）
- Embedding 状态
- 是否执行 Full Re-embed（完整重建向量）
- 是否发生 CPU 回退
- `PI_MEMORY_SNAPSHOT` 最终值
- `PI_MEMORY_QMD_UPDATE` 最终值
- `PI_MEMORY_SUMMARIZE_TRANSITIONS` 最终值
- Runtime 配置保存位置
- Runtime 配置备份路径
- QMD 配置备份路径
- PATH 是否被修改
- PATH 原值备份或记录位置
- 是否出现 `CHINESE_MODEL_MIGRATION_SKIPPED`
- `AGENTS_MD_MODIFIED: No`
- `SKILLS_MODIFIED: No`
- `MCP_SERVER_STARTED: No`
- `MCP_CONFIG_MODIFIED: No`
- 尚未完成或需要用户处理的步骤
- 关键错误摘要，但不得包含秘密信息

如果某个文件原先不存在，因此没有备份，应写明：

NOT_APPLICABLE_NEW_FILE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
十二、最终回复格式
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

最终回复使用简洁表格：

| 检查项 | 状态 | 说明 |
|---|---|---|
| pi-memory | PASS/PARTIAL/FAIL | 版本和安装范围 |
| QMD | PASS/PARTIAL/FAIL | 版本与命令路径 |
| pi-memory Collection | PASS/PARTIAL/FAIL | 实际绝对路径 |
| Qwen3 Embedding | PASS/PARTIAL/FAIL | 模型和向量状态 |
| Snapshot | PASS/PARTIAL/FAIL | stable |
| QMD Update | PASS/PARTIAL/FAIL | background |
| Transition Summary | PASS/PARTIAL/FAIL | 已设置为 1 |
| per-turn | PASS/PARTIAL/FAIL | 未启用 |
| QMD MCP Server | PASS/PARTIAL/FAIL | 未启动 |
| AGENTS.md | PASS/PARTIAL/FAIL | 未修改 |
| Skill | PASS/PARTIAL/FAIL | 未修改 |
| 安装报告 | PASS/PARTIAL/FAIL | 报告绝对路径 |

不要输出密码、Token、API Key、Cookie 或私钥。

当前会话安装完成后，如果当前 Pi 运行时尚未加载新扩展，最后明确要求用户在 Pi 中输入：

/reload

然后建议用户在重载完成后输入：

memory_status

不要让用户重新执行安装命令。

不要声称 Transition Summary 已经实际生成过摘要，除非后续某次真实的 `/new`、`/reload`、`/resume` 或 `/fork` 转换确实触发并写入摘要。

本次任务到生成安装报告和提示用户执行 `/reload` 为止。
