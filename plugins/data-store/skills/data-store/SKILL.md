---
name: data-store
description: 把已有结构化记录写入共享项目数据根目录，以 Parquet 内部 Zstd 保存，并通过 DuckDB 稳定逻辑表分批查询。只负责存储、写入、查询。
---

# Data Store（数据存储）

只保存已有记录，不运行模拟、不收集额外数据。所有任务共用调用方明确配置的项目级数据根目录，不按任务创建独立数据中心。

## 运行准备

需要 Python（编程语言）3.10 以上和本技能 `requirements.txt` 中固定的 DuckDB（分析查询引擎）。缺依赖时明确报告；安装到用户环境前取得授权。无需源码仓库、PyArrow（列式处理库）、服务或持久数据库。

入口是本技能 `scripts/data_store.py`，按实际安装目录解析，不能固定指向开发源码。下面 `<skill>` 是安装后的技能目录，`<data>` 是共享数据根目录。

## 写入

`python <skill>/scripts/data_store.py --root <data> write measurements batch_01`

从标准输入接收一个非空 JSON（数据交换格式）记录数组。记录在内存中转换为有类型的 Parquet（列式文件），仅 Parquet 持久化，内部压缩为 Zstd（压缩算法）。表名和记录键是逻辑身份，不区分大小写并统一为小写，不能传路径。

可使用 `--schema '{"label":"VARCHAR","score":"DOUBLE"}'` 明确字段及 DuckDB 类型；同一表应使用一致类型。未声明类型时使用 DuckDB 原生类型推断。文本数字不自动转换；嵌套对象和数组使用 STRUCT/LIST（结构体/列表）。字段结构不适合推断时提供明确类型，不静默回退到 JSON 文本列。调用方可以为单个元数据字段显式选择 JSON 类型，但业务适配不得把完整结果塞进不透明 JSON 列或另存完整副本。

同一表、同一记录键会原子替换完整记录组，其他键保留；调用者为每个正常批次选择稳定且唯一的键。单个写入处理调用者已经限定大小的一批记录。临时写入失败不会覆盖旧分片；不做备份、迁移或写后哈希回读。

Python 调用：`write(root, table, key, rows, schema=None)`；schema 是可选关键字参数，返回写入记录数。字段、类型和表名均由调用者定义，技能不绑定任何业务模型。

## 查询

`python <skill>/scripts/data_store.py --root <data> query 'SELECT label, score FROM measurements WHERE score > ?' --parameters '[10]' --batch-size 1000`

只接受一条 SELECT（只读查询），通过稳定逻辑表名访问所有已完成分片。命令按指定批量读取并逐行输出 JSON，不先生成完整结果列表。仅能读取配置的数据根目录，不自动安装扩展。

Python 调用：`query(root, sql, parameters=None)` 返回 DuckDB 游标；使用 `fetchmany(1000)` 分批读取，并用上下文管理器或 `close()` 关闭。不要让业务调用者直接读取 Parquet 路径。结果在查询启动后按当次执行读取；跨键批量事务及并发同键写入协调由调用方负责，不属于本技能。

### 已知记录键的点读

`python <skill>/scripts/data_store.py --root <data> read-key measurements batch_01 --batch-size 1000`

Python 调用：`read_key(root, table, key)`。表和键与 `write` 使用同一逻辑身份，返回该键的完整记录组游标，仍用 `fetchmany` 和上下文管理器关闭。只打开目标分片，不枚举其他表或历史分片；通用 `query` 的全表、多表语义不变。

数据根存在但目标键不存在时抛出 `MissingKeyError`（继承 `FileNotFoundError`）；明确的 Parquet 文件头或页脚损坏抛出 `CorruptDataError`。整个数据根不可用、权限、锁、磁盘及无法确定为内容损坏的查询错误原样传播，调用方不能把所有读取失败当作无效数据而静默重算。点读不做完整哈希复核或第二次完整报告读取；业务身份与成绩核验仍由调用者负责。

## 边界

生成数据、缓存、开发临时文件和测试均不放进技能目录。没有归档、恢复、预览、保留期、清理、容量、训练或后端框架。

复用来源：Quant-Research-Lab（量化研究仓库）提交 `4c9c7b8d30e1d899331465f37ed0ca44801f2797` 的原子发布短退避和内存视图做法；没有复制金融数据模型或依赖栈。
