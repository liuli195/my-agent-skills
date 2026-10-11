# Data Store

## Purpose

让调用者把已有结构化记录保存在一个项目级数据根目录，通过稳定逻辑表名写入和分批查询，不依赖开发源码位置或数据治理平台。

## Requirements

### Requirement: Data Store preserves caller-defined typed records in compressed Parquet

Data Store（数据存储）MUST（必须）按调用者定义的逻辑表、记录键、字段和类型保存已有记录；持久数据使用内部 Zstd（压缩算法）压缩的 Parquet（列式文件），不生成第二套完整结果或持久查询数据库。数值及适用的 STRUCT/LIST（结构体/列表）必须保持可查询，自动推断不得静默把完整结果退化成不透明 JSON（数据交换格式）文本。

#### Scenario: Caller writes typed records

- **WHEN** 调用者在项目级共享数据根目录写入一组有效记录，并按需指定字段类型
- **THEN** 记录以有类型的 Zstd Parquet 保存，并可通过对应逻辑表查询
- **THEN** 业务数据模型和表名由调用者决定，不要求采用特定模拟或金融模型

#### Scenario: Inference cannot preserve structured columns

- **WHEN** 字段自动推断只能退回不透明 JSON 类型
- **THEN** 写入明确要求调用者提供类型，不静默保存为不透明整份结果
- **THEN** 调用者仍可为单个元数据字段显式选择适用类型，但业务适配不得以此保存完整结果副本
### Requirement: Data Store replaces logical keys without exposing partial writes

Data Store MUST 将逻辑表名和记录键按一致、不区分大小写的规则解释，写入同一键时只替换该键的完整记录组。数据转换或临时写入失败 MUST 不覆盖已有完整数据；逻辑身份不能作为路径越过配置的数据根目录。

#### Scenario: Caller replaces an existing key

- **WHEN** 调用者使用大小写不同但相同的逻辑表和记录键写入新记录组
- **THEN** 查询只得到该键的最新完整记录组，其他键的记录保持可见

#### Scenario: Replacement fails

- **WHEN** 新记录不能满足声明类型或写入过程失败
- **THEN** 写入返回明确失败，原有完整记录仍可查询，不把部分新记录当成成功结果
### Requirement: Data Store exposes read-only logical-table queries with bounded consumption

Data Store MUST 通过 DuckDB（分析查询引擎）提供稳定逻辑表名和参数化只读查询，不要求正常调用者了解物理分片路径。查询结果 MUST 支持原生游标按有限行数分批消费，不能要求先构造完整结果列表。

#### Scenario: Caller queries multiple completed batches

- **WHEN** 调用者按逻辑表名查询多个已完成记录键，并指定查询参数
- **THEN** 查询返回对应结构化结果，调用者可逐批读取
- **THEN** 查询层不另存一份完整数据或自动安装查询扩展

#### Scenario: Caller requests a mutating statement

- **WHEN** 查询入口收到写入语句或多条语句
- **THEN** 查询拒绝执行，并明确指出只接受单条只读查询
### Requirement: Data Store runtime is independently discoverable and executable

Data Store MUST 提供可供 Codex/Claude（代理客户端）使用的自包含技能运行目录，只包含说明、运行脚本和必要资源及依赖声明；开发测试和生成数据必须留在该运行目录之外。运行只新增 DuckDB 直接依赖，不能要求从开发仓库其他目录导入实现。

#### Scenario: Agent invokes an installed skill

- **WHEN** 代理客户端发现安装或直接联接的 Data Store 技能，并使用已具备所声明依赖的 Python（编程语言）环境调用其入口
- **THEN** 写入和查询使用该技能自身运行脚本完成，不依赖开发源码工作树的固定绝对路径
- **THEN** 项目共享数据根目录独立于技能安装位置

#### Scenario: Runtime dependency is unavailable

- **WHEN** 当前解释器没有所声明的 DuckDB 依赖
- **THEN** 技能明确报告缺少依赖及准备方式，不自动修改用户环境或以其他存储方式伪装成功
### Requirement: Data Store reads known logical keys without scanning unrelated records

Data Store（数据存储）MUST 提供按逻辑表名和写入记录键读取完整记录组的入口，沿用写入时的名称、大小写、类型及同键替换规则；调用者不需要物理路径。按键读取 MUST 只访问目标已完成分片，支持原生游标分批消费和关闭，不枚举无关历史，不改变通用多表只读查询。

#### Scenario: Caller reads a known key

- **WHEN** 调用者通过独立安装后的技能，使用写入时的逻辑表和记录键读取已有记录组
- **THEN** 只读取目标记录组并保留数值及嵌套结构，支持分批消费，无关损坏分片不影响结果

#### Scenario: Caller replaces a key and reads again

- **WHEN** 调用者成功替换同一逻辑键后重新发起按键读取
- **THEN** 新调用获得该键的最新完整记录组，其他键保持可见，读取资源在正常或异常关闭时释放
### Requirement: Data Store distinguishes missing keys and definite corruption from storage failures

Data Store MUST 将数据根存在但目标键缺失、已明确识别的目标文件头或页脚损坏，与整个数据根不可用、权限、锁、磁盘及无法确定为内容损坏的读取错误分开报告。存储执行错误 MUST 原样传播，不能一概变成内容损坏或目标缺失。

#### Scenario: Target key is absent or definitely corrupt

- **WHEN** 数据根可用但目标键不存在，或目标列式文件头或页脚确定损坏
- **THEN** 调用者分别收到可区别处理的目标缺失或内容损坏错误

#### Scenario: Storage is unavailable or the cause is uncertain

- **WHEN** 整个数据根不可用，或读取因权限、锁、磁盘及不能确定为内容损坏的查询问题失败
- **THEN** 原始存储执行错误向调用者传播，不被当作无效数据，不自动安装依赖、修复或迁移数据
### Requirement: Data Store reads multiple logical keys and selected top-level fields

Data Store（数据存储）MUST 支持一次读取多个已知逻辑记录键，并可直接选择顶层字段；调用者使用写入时的表和键，不提供文件路径。未选择字段时返回完整记录；记录键按既有大小写规则去重，跨键结果顺序不作保证，结果保留类型并支持分批消费及关闭。任一目标缺失、明确损坏或暂时不可用 MUST 报告对应失败，不静默跳过目标。

#### Scenario: Caller reads several keys and selected fields

- **WHEN** 调用者通过独立安装后的技能一次指定多个记录键，以及可选的顶层字段名
- **THEN** 只读取指定目标及字段，重复键不重复返回记录，无关历史或损坏分片不阻塞目标读取
- **THEN** 字段保持可查询的结构化类型，仍可分批消费并关闭结果

#### Scenario: Caller supplies invalid keys or fields

- **WHEN** 调用者提供空键列表、空字段列表、非法键、重复字段或未知字段
- **THEN** 读取明确报错，字段名按名称处理，不当作查询表达式执行，不返回部分成功结果冒充全部成功
### Requirement: Data Store keeps reading optimization transparent and data current

Data Store MUST 在内部选择合适的读取配置，不要求调用者提供调优参数；优化 MUST 保留完整逻辑表、多表参数化只读查询、数据根限制和错误含义，不要求业务文件名，不预载全部历史、不保存第二套完整结果或常驻查询连接。内部记住的配置选择 MUST 不使后续读取返回过期数据。

#### Scenario: Caller uses generic logical-table queries

- **WHEN** 调用者通过原有通用入口按逻辑表、字段和参数进行完整、嵌套、多表或统计读取
- **THEN** 原有查询和类型继续有效，调用者无需另选读取配置；全部合法逻辑表仍准备检查，无关表损坏仍明确失败

#### Scenario: Caller reads after stored records change

- **WHEN** 同键成功替换、增加记录键或删除分片之后，调用者再次发起读取
- **THEN** 新读取看到当次可用数据，不复用旧结果；单键完整读取保持兼容，字段或来源无法明确识别时仍正常使用默认配置执行
### Requirement: Data Store selects fields and matching rows within logical record groups

Data Store（数据存储）MUST（必须）在按单个或多个逻辑记录键读取时，支持可选顶层字段和顶层字段标量等值条件，在查询中选择匹配记录而不要求调用者先接收完整组。条件支持字符串、数值、布尔值及空值，多个条件同时成立；字段名按名称处理，条件值按参数处理，不能作为查询表达式执行。调用者 MUST 不需要物理路径、业务专用字段或调优参数；保留字段类型、分批消费、关闭资源和既有错误含义，不另存完整结果或持久数据库。没有选择字段或筛选条件时，原有完整组读取语义 MUST 保持兼容。

#### Scenario: Caller selects fields from one logical key

- **WHEN** 调用者指定一个已有逻辑记录键和顶层字段名
- **THEN** 只返回选定字段，保留数值及嵌套类型，不要求提供物理文件路径

#### Scenario: Caller selects matching rows from one or several keys

- **WHEN** 调用者读取一个或多个已有逻辑键并提供有效等值条件，包括空值条件
- **THEN** 只返回同时满足条件的记录及选定字段，重复键不重复返回记录，仍可分批读取并关闭

#### Scenario: Caller supplies an invalid filter

- **WHEN** 调用者提供空条件、非标量条件值或不存在的顶层字段
- **THEN** 读取明确报错，不执行字段名或条件值中的查询表达式，不返回部分成功冒充全部成功

#### Scenario: Caller omits selection and filters

- **WHEN** 调用者按原有逻辑表和键读取而未指定字段或条件
- **THEN** 返回原有完整记录组，替换后的新读取看到最新数据，缺失、明确损坏或暂时不可用仍按原错误规则报告
### Requirement: Data Store ships a ready-made project connection for all integrated consumers

Data Store（数据中心）MUST 随市场技能提供现成的项目接入、检查与更新入口，由代理从实际已安装技能入口调用，依据自身安装位置建立一个项目共用连接。所有接入工具与独立命令 MUST 使用同一连接；正常运行不需要用户填路径、启动方传位置、第三方定位工具、客户端查询、缓存目录猜测或另装 NPM（软件包管理器）程序。项目数据根独立于安装位置，接入关系只保留本机，不复制实现或提交本机绝对位置。

#### Scenario: An agent connects an installed skill to a project

- **WHEN** 用户安装插件后让代理将数据中心接入目标仓库
- **THEN** 代理直接调用随包接入入口，项目内所有已对接调用者共用实际安装实现
- **THEN** 重复接入同一来源安全，独立命令和同进程调用均能写入、查询同一共享数据
### Requirement: Data Store changes project connections safely and keeps running implementations explicit

Data Store MUST 在更新项目连接前检查新安装可用与原来源相符；普通文件、目录或重定向父目录冲突时明确拒绝并保留内容。切换失败 MUST 恢复旧入口；恢复或清理也失败时分别保留原始错误和可恢复位置。只清理连接本身，不能删除安装目标或用户数据。新机器或工作树重新接入一次，已运行进程更新连接后重新启动，正常读写不重复定位。

#### Scenario: A connection update succeeds or fails

- **WHEN** 代理从新的已安装技能入口更新已核对旧来源的项目连接
- **THEN** 成功后新命令使用新来源，已加载实现的进程在重启后切换
- **THEN** 更新失败仍可恢复旧入口；连续失败明确保留错误与旧入口位置，不伪报成功
### Requirement: Data Store connection changes preserve logical-table behavior and measured performance

Data Store MUST 保持既有逻辑表、写入替换、只读查询、点读及批量指定字段的语义和类型；安装接入变化不能增加正常每次读写的进程启动或客户端查询。交付前 MUST 以相同真实数据、环境、线程策略及实际工作量交替比较既有读写、冷启动和独立命令，记录结果与测量波动；超过正常波动的稳定退化必须解决，不以其他场景收益抵消。

#### Scenario: An integration change is validated for delivery

- **WHEN** 数据中心接入实现准备交付
- **THEN** 相同输入的写入、替换、单键、多键、字段筛选、嵌套报告、平坦事件、统计与多表查询返回一致内容及类型
- **THEN** 首次加载与重复进程内读写分开测量，稳定退化未解决时不交付
