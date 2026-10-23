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

Data Store（数据存储）MUST 提供按逻辑表名和写入记录键读取完整记录组的入口，沿用写入时的名称、大小写、类型及同键替换规则；调用者不需要物理路径。按键读取 MUST 只访问目标已完成分片，支持原生游标分批消费和关闭，不枚举无关历史，保留通用入口显式声明表范围内的多表只读查询。

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
- **THEN** 原有查询和类型继续有效，调用者无需另选读取配置；只准备显式声明的逻辑表，无关表损坏不影响目标读取，目标表损坏仍明确失败

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
### Requirement: Data Store requires explicit logical tables for generic queries

Data Store（数据存储）MUST（必须）提供 query(root, sql, parameters=None, *, tables)（显式表查询），tables 必须为非空列表或元组，沿用原逻辑名称和大小写去重规则。命令行查询 MUST 提供 --tables（表范围）。漏传、空值、空范围、非法名称与非单条只读语句 MUST 在枚举目标目录前失败；使用查询引擎原生语句类型检查，不自写查询解析器。查询 MUST 只枚举和登记声明表的已完成分片，不推测补表或回退全库；多表参数化查询、字段合并、嵌套类型及分批游标 MUST 保持。

#### Scenario: Caller scopes a query around unrelated history

- **WHEN** 调用者声明目标逻辑表并发起只读查询，其他表含损坏文件或非法目录
- **THEN** 只准备目标表并返回对应结果，不枚举或读取无关业务数据

#### Scenario: Caller declares absent or empty tables

- **WHEN** 调用者声明不存在或没有已完成分片的表
- **THEN** 系统表检查返回不存在，普通目标读取返回查询引擎缺表错误，不从其他表猜测结构
### Requirement: Data Store restricts business files while preserving native temporary spilling

Data Store MUST 仅把选定业务分片加入原生显式文件许可名单，关闭外部访问与自动扩展并锁定配置；未声明业务表及文件不得自动加入范围，表目录和分片不得通过链接重定向到其他表或数据根之外，已知键读取适用同一规则。引擎既有临时溢写目录和内存策略 MUST 保留；该目录是明确例外，不承诺阻止人工查询读取其中的文件，正常业务不得以其作为业务数据源。此入口不构成任意查询的绝对文件安全沙箱，不新增临时目录管理、清扫或查询解析器。

#### Scenario: Caller attempts an undeclared business source

- **WHEN** 调用者查询未声明业务表或直接请求其文件
- **THEN** 原生引擎拒绝该业务源，查询不扩大范围或重试全库

#### Scenario: Engine retains ordinary memory and spilling behavior

- **WHEN** 调用者通过查询或点读入口读取声明的业务数据
- **THEN** 选定文件许可和配置锁定生效，原有临时溢写目录保留，不通过关闭溢写改变大查询内存行为
### Requirement: Data Store exposes an exact capability version at module load

Data Store MUST 提供 DATA_STORE_API_VERSION = 2（接口能力版本二）；消费者 MUST 在加载实现时检查值确切为二，缺失或不匹配明确要求同步并重启，不静默接受旧能力或在每次查询时检查安装状态。Data Store MUST 通过 DATA_STORE_CAPABILITIES（接口能力集合）声明 binary-write-v1（原生二进制写入第一版）；需要此能力的新消费者 MUST 在实际加载的模块上核验其存在，缺失时停止并要求同步技能后重启，不静默降级编码。原有不使用此能力的消费者不需要新增能力要求。能力常量不得冒用尚未发布的发行版本，开发验证不得更换全局安装。

#### Scenario: Consumer loads a matching or mismatching implementation

- **WHEN** 消费者加载项目共用入口中的实现
- **THEN** 确切版本二可使用显式表查询；缺失或不匹配时停止正常读取并明确报告同步需求

#### Scenario: Consumer needs native binary writes

- **WHEN** 消费者需要原生二进制写入并加载实际安装的实现
- **THEN** 消费者在确切接口版本二之外核验 binary-write-v1 能力，缺失时明确停止并要求同步后重启
- **THEN** 项目连接检查或发行版本名称不能替代实际能力检查，既有不使用二进制能力的调用不受新增能力要求影响
### Requirement: Data Store defines identity-aware caller reuse requirements

Data Store（数据存储）MUST（必须）在接入说明中要求调用项目声明资料的完整业务身份、可变性、解释版本与复用有效范围。不可变资料在完整身份与解释版本相同时复用；可变资料按可信权威版本核验后复用。调用者必须优先使用适合其需要的既有按键、字段选择、筛选及批量读取能力，避免不必要的大对象转换、完整复制、重复扫描和多份等价完整结果。版本核验、失效、失败确认及恢复所需的重复访问允许保留，但项目须说明原因；本要求不新增存储接口或常驻缓存。

#### Scenario: Caller reuses stable data and reacts to changes

- **WHEN** 调用者按技能说明接入需要重复消费的业务资料
- **THEN** 接入约定明确完整身份、权威版本依据、有效范围和失效方式，不把同一个文件名或记录键当作内容永久不变
- **THEN** 有效身份或版本未变时复用已加载对象，变化或必要失败确认时重新核验，不为减少读取而跳过正确性检查

#### Scenario: Caller persists recoverable results

- **WHEN** 调用者需要保存能够在后续恢复的业务结果
- **THEN** 说明要求先成功持久化权威资料，再发布包含必要身份和版本的引用，优先避免多份等价完整结果
- **THEN** 缺失、明确损坏和暂时不可用保持区分，不以性能优化为由静默补算或替换业务结果
### Requirement: Data Store requires caller-owned access verification evidence

Data Store（数据存储）MUST（必须）要求调用项目从其现有真实用户入口提供数据访问与复用的完成证据，不能仅凭统一接口调用或连接检查通过宣称接入完成。证据必须覆盖实际访问路径、规模、身份与版本依据、所取字段和调用次数、结果一致性、必要更新与恢复，以及代表实际成熟使用规模的成本。说明必须区分接口调用次数与物理输入输出次数、单次内存查询连接与长期业务缓存；不设未经测量的通用固定秒数门槛，不要求以全量搜索或大量随机样本证明一次接入。

#### Scenario: Caller demonstrates access behavior

- **WHEN** 调用项目报告数据存储接入完成
- **THEN** 项目提供经真实存储接口执行的必要场景证据，包括稳定身份或版本复用、变化后更新、失效及失败恢复，计数记录不复制完整大对象
- **THEN** 小样例仅作为基本功能证据，不能代替实际规模的成本与正确性验证，也不把连接检查当作性能合格证明

#### Scenario: Maintainers place verification in the owning repository

- **WHEN** 维护者为存储能力或调用项目补充验证
- **THEN** 存储自身的公开接口及安装形态测试留在技能源码仓库，业务身份、复用、恢复和实际规模测试留在调用项目仓库
- **THEN** 业务数据根目录不存放测试代码或验证报告，安装后的技能目录不存放生成数据、缓存、临时产物或测试
### Requirement: Data Store explicitly opts in to native top-level binary writes

Data Store（数据存储）MUST（必须）在现有公开 write（写入）入口提供默认关闭的 binary（原生二进制方式）关键字。显式开启时 MUST 要求非空字段类型声明，仅顶层声明为 BLOB（二进制字段）的值接受 Python（编程语言）原生 bytes（字节串）或 None（空值），保留任意字节、空字节串与空值的区别。普通字段 MUST 沿用现有显式类型转换的合法转换及失败行为；多行、多二进制字段及纯二进制字段记录 MUST 保持每行完整对应，通过原有单份有类型压缩记录原子替换，不产生旁路副本。默认关闭时 MUST 保持原有导入、类型推断及旧 BLOB 字符串写入行为，不因字段类型声明而自动切换方式。既有公开读取入口 MUST 保留原生字节值、字段选择、筛选、错误区分与读取安全限制。存储层不解释字节内容，不规定业务矩阵或模型协议，完整业务结果不得整体退化为不透明二进制字段。

#### Scenario: Caller writes native binary fields and typed metadata

- **WHEN** 调用者显式开启原生二进制方式，并以完整字段类型声明写入多行普通元数据及一个或多个顶层二进制字段，或只含二进制字段的记录
- **THEN** 既有公开读取入口返回对应的原生字节、空值及有类型元数据，行与字段不发生错配，空字节串不变为空值
- **THEN** 同键替换仍只发布一个完整记录组，转换或临时发布失败不覆盖旧完整数据

#### Scenario: Caller provides invalid native binary records

- **WHEN** 调用者开启原生二进制方式却未提供有效字段类型、记录缺少或多出声明字段、字段名称冲突，或为二进制字段提供非字节非空值或嵌套原生字节
- **THEN** 写入在发布前明确失败，不静默转换、创建部分成功记录或覆盖旧完整数据

#### Scenario: Caller keeps the existing write mode

- **WHEN** 调用者省略或关闭原生二进制方式，包括已有显式 BLOB 类型与字符串值的调用
- **THEN** 原有类型推断、转换、接受与失败行为保持不变，不自动启用只接收原生字节的新方式
### Requirement: Data Store rejects lossy binary command-line output

Data Store MUST 保留命令行普通记录写入及元数据读取，不新增二进制输入协议。查询、单键读取和多键读取的结果字段类型直接或通过复合类型包含 BLOB 时，命令行 MUST 在输出记录前明确拒绝并提示选择普通元数据或在查询中显式编码，不能把字节串静默转为看似可恢复的字符串。Python 现有读取入口仍返回原生 bytes，命令行显式编码得到的普通文本结果继续正常输出。

#### Scenario: Command-line caller selects metadata or encoded text

- **WHEN** 调用者通过现有命令行读取普通元数据，或查询显式编码后的普通文本字段
- **THEN** 读取继续正常输出原有结构化文本结果，无需取得完整二进制内容再由调用者删除

#### Scenario: Command-line caller selects a binary result

- **WHEN** 调用者通过查询、单键或多键命令直接读取类型含 BLOB 的结果，包括空结果、空值或嵌套二进制字段
- **THEN** 命令在输出记录前明确失败并提供选择元数据或显式编码的提示，不输出有损二进制字符串冒充成功
### Requirement: Data Store previews exact offline deletion targets without changing data

Data Store（数据存储）MUST 提供公开命令与 Python（编程语言）入口，按非空逻辑表与精确记录键映射预演永久删除完整记录组，沿用已有名称及大小写规范并去重。预演只访问明确目标，不枚举无关历史，不接受通配符、全表、全库、任意路径或行级删除。业务引用、保留条件及允许删除哪些目标由调用项目确定，技能不推断孤儿或删除业务锁。

计划 MUST 绑定唯一计划身份、精确数据根及其文件系统身份、规范化目标、目标目录与文件实例及内容身份；同名或同内容的替换文件也不能自动成为原计划目标。目标缺失、不可读、重定向或身份不足时明确失败，不生成可执行的部分计划。预演不改变业务数据；计划输出须可经受支持的命令行编码保存和重新读取，非英文路径不得在往返时被静默改写。

#### Scenario: A caller previews known record groups

- **WHEN** 调用方提供合法非空逻辑表及精确键，包括大小写重复目标
- **THEN** 预演只核验规范化去重后的目标并输出完整身份计划，业务文件不被修改，无关损坏分片不被读取

#### Scenario: A target or requested scope is invalid

- **WHEN** 范围为空、含非法名称或通配符，或目标缺失、不可读及通过链接重定向
- **THEN** 预演明确拒绝，不扩展扫描全库，也不提供缺项计划冒充完整授权范围
### Requirement: Data Store executes an approved offline plan against unchanged file identities

Data Store MUST 在永久删除前要求明确匹配完整计划身份的批准，以及调用方已确认并持续维持无相关活动读写和其他维护进程的离线前提。计划和回执保存在业务数据根之外的调用项目位置，不覆盖其他计划的回执；执行不替用户停止进程、探测或删除业务锁，也不把离线参数冒充并发锁或对不合作写入者的绝对竞态防护。

执行 MUST 在任何删除前完整预检全部尚未可靠完成的目标，并在每项删除前再次核验其原目录、文件实例及内容身份。计划被修改、数据根不可用、文件缺失、权限／锁故障、重定向、非普通文件或身份变化时如实区分失败；完整预检失败不得删除任何业务目标，执行期间检测到漂移须保留该目标并停止后续删除，不用旧授权删除同键新内容。

批量执行 MUST 明确声明非原子，输出每项目标及原身份、可靠完成、明确失败、未执行或不确定结果，并汇总全部完成、未完成或存在不确定项；仅全部可靠完成时成功退出。不备份已删文件，不因后项失败伪称此前删除已回滚，也不把原先缺失的文件计作本次删除。删除后持久回执或必要目录同步失败须报告不确定结果，不伪造可靠完成。

#### Scenario: The exact plan is approved for offline execution

- **WHEN** 调用方批准该完整计划并确认离线，所有未完成目标通过预检和逐项最终核验
- **THEN** 仅删除原计划对应文件，保存真实逐项结果并明确非原子；所有目标可靠完成后才返回整体成功

#### Scenario: A target changes before deletion

- **WHEN** 预演后或完整预检后，目标被替换、内容变化、消失或发生目录重定向
- **THEN** 不删除该变化目标，明确报告失败或结果状态，不将同键新文件纳入旧计划批准范围

#### Scenario: Execution stops after partial progress

- **WHEN** 前项已可靠删除而后项失败，或删除已发生但结果无法可靠持久化
- **THEN** 分别报告已完成、失败、未执行及必要的不确定项，不声称整批原子完成或已回滚
### Requirement: Data Store resumes exact maintenance plans without repeating completed deletions

Data Store MUST 通过相同计划及其可靠回执继续未完成维护，核验两者精确对应，顺序读取一次日志并重新核验未完成目标身份。已可靠完成项不重复删除，即使相同键后来创建新文件也必须保持；缺失、变化或不适用的未完成目标不能被静默跳过为成功。

回执 MUST 保留完整原身份及逐项可恢复进度，正常写入量随目标数线性增长，不反复重写整批清单。无效、截断或不完整日志须阻止继续，不静默修剪；存在任何不确定项时整个调用不再删除，要求调用项目先核实实际结果，不提供猜测成功、强制重试或另造计划绕过不确定结果的路径。这里的恢复是继续执行，不是恢复已删除数据。

维护 MUST 以有界内存核验明确目标，成本随这些目标字节数增长；不在正常写入、查询和点读热路径增加维护、散列、后台检查、长期连接或依赖。原接口能力版本二、原生二进制写入、类型及既有错误含义保持；调用方需在实际加载的模块核验精确维护能力，不能用发行版本或连接检查代替能力证明。

#### Scenario: A plan resumes after a definite partial failure

- **WHEN** 原计划及回执可核验且没有不确定项，部分目标已可靠完成，其他目标仍保持原身份
- **THEN** 只处理尚未完成项，跳过已完成项及后来同键重建文件，保留真实累计结果，不把以前完成记为本次新删除

#### Scenario: A receipt is uncertain or damaged

- **WHEN** 回执包含不确定项、属于其他计划、被截断或无法完整解析
- **THEN** 本次不再删除，保留原计划、回执和现存数据并报告具体阻塞，不自动丢弃证据后重试

#### Scenario: Ordinary data access continues after maintenance is introduced

- **WHEN** 调用方使用既有写入、二进制写入、单键、多键或显式表查询入口
- **THEN** 原类型、能力、错误和当前数据语义保持，不为新增维护增加逐次散列或后台扫描
