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
