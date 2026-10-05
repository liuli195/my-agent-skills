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
