# 01：固定数据存储接入的性能复用要求

Parent: [本次规格](../spec.md)
Status: ready-for-human
Blocked by: 实施范围无未解决阻断；待主代理提交证据收尾并固化最终提交头验证。正式规格应用及PR（拉取请求）交付尚未执行；无其他票据依赖。

## What to build

更新现有数据存储技能，使接入者必须明确数据身份、可变性、版本、读取范围、对象复用与恢复资料保存方式，并提供来自项目真实入口的必要验证证据。复用现有脚本及验证项，不新增性能检查框架，不迁入GSE（序列模拟项目）业务测试。

## Acceptance criteria

- [x] 技能明确不可变资料完整身份复用、可变资料版本核验复用及必要失效条件，不一刀切禁止合理重复。
- [x] 技能要求优先复用现有按键、字段选择及批量读取，避免不必要的大对象转换、复制和重复扫描。
- [x] 技能区分一次内存查询连接与常驻结果缓存，不把现有连接检查等同于性能通过。
- [x] 技能要求先持久化权威资料再保存引用，缺失或不确定状态不静默补算或改变业务结果。
- [x] 接入完成要求包括实际调用路径、访问次数与字段、结果正确性、版本变化/恢复和实际规模测量，说明接口次数不是物理I/O（输入输出）次数。
- [x] 数据中心自身测试、调用项目测试和业务数据目录的边界清楚；不新增不必要的通用脚本、配置或命令行。
- [x] 复用既有构建与验证入口，核对安装形态与受影响检查，提交证据和独立审查；未授权发布、安装或应用正式规格。
- [x] 按用户后续明确调整，将Pytest（测试框架）固定为9.1.1，核对现有插件及开发依赖兼容，并通过既有公开入口验证受影响范围；不安装新包或擅改无关失败。

## Public seam

安装形态的技能说明及已有公开写入、查询、按键读取入口。文档要求的业务验证由业务项目真实入口承担，不用插件内部单元测试冒充整项目性能证明。

## Evidence and status

### 实施范围与文档红绿核对

- 2026-10-18（UTC）在已确认工作树及分支实施；固定基线为`767d4ee456cc841cd20189e2865bb2044d0be219`。主代理负责全部Git（版本管理）操作，实施者未暂存或提交。
- 原接入契约仅修改`plugins/data-store/skills/data-store/SKILL.md`；用户后续明确追加的测试框架升级只修改`requirements-dev.txt`，本次规格与本票据同步该调整及状态和证据。未改脚本、测试、验证配置、接口、数值表示、缓存行为、发行版本、业务数据或安装位置，未写`myspec/specs/`。
- 文档红证据：基线技能说明共78行，Git文件对象为`201c7791e61fe208ea71eaaf3ff676b2209f944d`；“接入项目”只说明连接与更新，“边界”只要求测试不进技能目录，缺少完整身份/权威版本复用、先持久化再引用、项目真实入口证据和三类测试归属约定。
- 文档绿证据：从同一技能入口重新逐项阅读，“调用方接入契约”覆盖前两项及权威资料引用；连接检查与“查询”说明一次内存连接及仅调参选择；“接入完成证据”覆盖实际调用、字段、版本/恢复、结果和代表规模成本；“边界”区分技能仓库、调用项目仓库与业务数据根目录。具体GSE（序列模拟项目）的业务测试属于Wow（魔兽世界插件）仓库，不迁入通用技能；本次未新增通用调用记录器、扫描器、规则配置、独立命令行或开发门禁。前六项验收已逐项核对，不把文字核对当作业务性能测试。
- 此次无运行行为变更，按测试驱动开发技能的适用边界保留可观察说明缺口到修改后核对的证据，不为文字匹配新增脆弱测试。

### 已有公开入口冒烟

使用现有测试中的临时安装副本、项目共用入口及真实公开脚本，不安装到用户环境；测试实现仍在本技能仓库，未修改Wow仓库文件。复用已有环境的Python（编程语言）3.12.14、Pytest（测试框架）9.1.1及DuckDB（分析查询引擎）1.5.6，未安装依赖。

```bash
PYTHONDONTWRITEBYTECODE=1 /workspace/shared/wow-addons/.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_data_store.py::test_independent_skill_cli_writes_and_queries_typed_rows \
  tests/test_data_store.py::test_typed_replacement_is_atomic_and_query_is_read_only \
  tests/test_data_store.py::test_key_read_distinguishes_missing_corrupt_and_unavailable \
  tests/test_data_store.py::test_batch_reader_preserves_types_failures_and_current_data \
  tests/test_data_store_project_binding.py::test_installed_connection_serves_other_commands_and_is_repeatable \
  tests/test_data_store_project_binding.py::test_update_restores_old_entry_when_filesystem_rename_fails
```

结果：`7 passed in 1.68s`，退出码0。覆盖安装形态的有类型写入、查询、按键/按列批量读取、同键更新、原子写入失败后旧值保留、缺失/损坏/不可用区分、项目入口读写及更新失败恢复。这里只证明原有公开能力与安装形态未受影响，不代表GSE业务性能已通过。

### 固定基线验证的实际结果与限制

- 主代理串行提交后，在干净工作树的提交`2978907c78ab053b538bf0d5e3fcf198aa430575`上运行仓库已有公开命令行入口，验证基线保持`767d4ee456cc841cd20189e2865bb2044d0be219`。首次命令使用下述入口和参数，但未设置`PYTHONPATH`（模块搜索路径）及`npm_config_cache`（软件包缓存目录）。

```bash
PATH=/workspace/shared/wow-addons/.venv/bin:$PATH \
BUILD_AND_VERIFY_PYTHON=/workspace/shared/wow-addons/.venv/bin/python \
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH} \
npm_config_cache=/workspace/shared/cloud-toolchain/npm-cache \
node plugins/build-and-verify/bin/build-and-verify.js verify \
  --project /workspace/shared/cloud-skills-bootstrap \
  --base 767d4ee456cc841cd20189e2865bb2044d0be219 --execution-context cloud
```

- 首次结果为`status: failed`（失败）、退出码1；实际选中`verify.local-build-contract`（本地构建契约检查）及`verify.data-store`（数据存储检查）。数据存储检查`34 passed in 5.41s`（34项通过）；构建契约检查3项失败、81项通过，其中2项因虚拟环境未能导入已有PyYAML（配置读取库），1项因软件包打包尝试写默认`/home/agent/.npm`路径而失败。
- 环境恢复只对本次命令引入宿主已有PyYAML（配置读取库）6.0.3及已有云端软件包缓存目录；没有安装依赖、修改依赖文件、持久配置或源码。恢复后实际导入仍为Pytest（测试框架）9.1.1、DuckDB（分析查询引擎）1.5.6及pytest-xdist（并行测试插件）3.8.0。
- 同一入口与固定基线重跑，实际输出`status: passed`（通过）、`checked: verify.local-build-contract, verify.data-store`（两项已检查）、`full-not-run: true`（未运行完整验证），退出码0。构建契约检查`84 passed in 2.60s`（84项通过），随后Node（运行环境）契约测试4项通过；数据存储检查使用有效缓存命中，实际执行证据为首次的34项通过。
- 当时的依赖限制：提交中的`requirements-dev.txt`要求`pytest>=7.0,<9.0`，复用环境9.1.1不符合。工具报告通过只说明上述实际执行结果，当时未据此签收符合仓库依赖的正式验证，也未安装隔离环境。用户后续已明确选择升级本仓库依赖，见下一节；不得把此旧提交的结果冒充新依赖差异已完成验证。

### 用户追加的测试框架升级

- 用户消息`Sentinel_7a086f69f32c8191bbbf358a9534d9dd`明确要求将技能仓库的Pytest（测试框架）升级为9.1.1。本次只把`requirements-dev.txt`中的`pytest>=7.0,<9.0`改为`pytest==9.1.1`，保留其他依赖约束及原有公开验证配置；不再安装8版隔离环境，也不安装新包。
- 读取现有开发依赖、验证配置、持续集成安装引用及`tests/conftest.py`（共享测试准备）后，未发现更严格版本策略。原有红证据是实际9.1.1不满足旧约束；声明更新后实际版本满足新精确约束，随后已运行原有公开入口验证受影响范围，结果见下一节，没有仅改版本号就判完成。
- 已安装包元数据核对：现Python（编程语言）3.12.14满足Pytest（测试框架）9.1.1要求的3.10以上；仓库声明范围内的第三方测试插件pytest-xdist（并行测试插件）3.8.0要求`pytest>=7.0.0`及`execnet>=2.1`（进程通信依赖），现9.1.1及2.1.2满足。现pluggy（插件机制库）1.7.0满足`>=1.5,<2`，iniconfig（配置解析库）2.3.1满足`>=1.0.1`，packaging（包元数据处理库）26.3满足`>=22`，pygments（语法高亮库）2.21.0满足`>=2.7.2`；PyYAML（配置读取库）6.0.3、DuckDB（分析查询引擎）1.5.6继续满足仓库原声明。只读核对仓库声明范围内、当前平台生效的9个已安装依赖闭包无不匹配，退出码0，原始输出块为`e7309e`；该闭包不涵盖宿主额外插件，本次运行宿主另自动加载AnyIO（异步兼容测试插件）4.14.2，因此不是只加载仓库声明插件的隔离环境。此元数据核对不替代正式验证。
- 已核对[官方Pytest（测试框架）9.1.1变更记录](https://docs.pytest.org/en/stable/changelog.html#pytest-9-1-1)及[pytest-xdist（并行测试插件）3.8.0发布页](https://pypi.org/project/pytest-xdist/3.8.0/)，兼容判断以本次实际包元数据和真实检查结果为证据，不由版本号单独保证。
- `requirements-dev.txt`已是多个现有验证检查的受影响路径和缓存输入，主代理串行提交形成干净工作树后，已用同一固定基线和公开入口运行实际选中的快速检查，没有自行缩减范围、安装新包或修改无关代码，也未运行未经批准的完整验证。

### 依赖升级后的正式验证

- 验证提交为`c28b4d31459b1683aad6885ad52591bb0573aaad`，固定基线仍为`767d4ee456cc841cd20189e2865bb2044d0be219`，使用前述同一公开命令及临时进程环境。实际结果为`status: passed`（通过）、退出码0，`full-not-run: true`（未运行完整验证）；本次7项检查均实际执行，没有缓存命中。
- 实际`checked`（已检查）范围及结果：`verify.local-build-contract`（本地构建契约）84项通过，另4项Node（运行环境）契约测试通过；`verify.release-flow`（发布流程）107项通过、1项跳过；`verify.pr-flow`（拉取请求流程）325项通过、5项跳过；`verify.runtime-boundaries`（运行边界）11项通过；`verify.build-and-verify`（构建验证插件）226项通过、2项跳过；`verify.build-and-verify-cli`（构建验证命令行）53项通过、2项跳过；`verify.data-store`（数据存储）34项通过。合计840项Pytest（测试框架）测试通过、10项跳过，另4项Node（运行环境）测试通过；跳过项不计为通过，不宣称完整或跨平台验证已完成。
- 原始标准输出及错误经`tee`（同步保存输出）写入仓库现有本地记录位置`.local/data-store-access-contract-verify-c28b4d3.log`，包括实际命令及`command-exit-code: 0`（命令退出码0）；启用管道失败传播并保留验证进程退出码，日志写入不掩盖验证失败。日志3267字节，SHA256（文件摘要）为`de5006ac4ba36de5d7f12c950af83c5608c395666393c4adffec109c320305cc`；执行器会话`70228`、输出块`694ea5`是对应原始执行记录。日志位于忽略目录，不进入提交，未新增验证入口。
- 验证后当前提交和分支未变，工作树干净；固定基线到工作区的差异空白检查通过，已跟踪及未跟踪正式规格路径检查均为空。实施范围验收已完成；本次仅回填证据，待主代理串行提交后通过同一官方入口固化最终提交头验证。

### 输出来源、审查与待完成

- 定向冒烟原始标准输出来自执行器会话`40040`、输出块`474dcb`；首次固定基线验证来自会话`50241`、输出块`ed374f`；环境恢复后的通过结果来自会话`98553`、输出块`db9dec`。这些是本次执行记录中的原始输出引用，不是仓库日志文件。
- 旧提交两次快速云端验证未生成统一结果JSON（数据交换格式）文件或独立日志文件，当时的成功缓存为`.build-and-verify/cache/c44f6bc3f649824240ecf6af3f9c67050fc999b2f909092385874a66891b7247.json`（数据存储检查）与`.build-and-verify/cache/ef5986cf15d499a6c3e1b40ecad62d9d4825224c7db5bc9edacf35646047d2e3.json`（构建契约检查）；各自仅记录检查标识及通过状态，不把缓存当作完整结果报告或业务性能证明。依赖升级后的原始日志见上一节。
- 原接入契约独立审查的规格轴无发现，规范轴仅提出P3（轻微问题）的术语中文释义修正；指定释义及末尾多余空行已修正关闭。追加依赖与文字修正的增量双轴独立审查已收口，无阻断项；其P3（轻微问题）依赖范围措辞已在本次收尾中限定为仓库声明范围，并明确宿主额外加载的AnyIO（异步兼容测试插件）4.14.2。未改技能正文、接口或测试。
- 本票据所列实施与验证范围已验收，保持门禁一的收尾范围；尚未加载或执行门禁二交付动作。正式规格应用、PR（拉取请求）交付、主干合并、发布及用户环境安装均未执行。
