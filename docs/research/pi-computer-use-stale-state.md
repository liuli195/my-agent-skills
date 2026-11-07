# `pi-computer-use` 0.4.3 Windows 操作失败调查

调查日期：2026-07-26

## 结论

`State is stale: expected epoch 0, current epoch 1` **不是最初故障，而是重试旧状态产生的后续保护错误**。

本次实际调用顺序是：

1. `observe_ui` 成功，得到版本 0 的状态；
2. 首次 `act_ui` 使用窗口根节点 `@e1`，原生层返回 `Element reference is stale`；
3. 0.4.3 的写入调度器在执行动作前已把资源版本从 0 推进到 1；
4. 再用原来的 `stateId` 重试时，调度器按设计返回 `expected epoch 0, current epoch 1`。

因此，先前“computer-use 不可用”的判断不准确。严格使用全新观察状态验证后：

- `observe_ui(mode="fused", image="always")` 获取带图像的状态；
- 使用坐标执行 `META+S`；
- `act_ui` 成功并返回后继状态。

这证明 Windows helper（辅助程序）、状态调度和坐标操作均可用。失败点是当时选择的语义窗口根引用，而不是整个 computer-use（电脑操作）失效。

## 源码证据

- `ResourceScheduler.write()` 会在派发原生动作前先递增版本；动作随后失败，旧状态仍保持失效。这是源码明确说明的失效优先设计：  
  https://github.com/injaneity/pi-computer-use/blob/v0.4.3/src/runtime.ts#L85-L94
- 所有桌面动作先通过该写入门禁：  
  https://github.com/injaneity/pi-computer-use/blob/v0.4.3/src/bridge.ts#L420-L429
- Windows 原生层会对已失效的元素句柄返回 `Element reference is stale`：  
  https://github.com/injaneity/pi-computer-use/blob/v0.4.3/native/windows/bridge-rs/src/main.rs
- 0.4.3 引入了不可变、按资源版本控制的状态模型：  
  https://github.com/injaneity/pi-computer-use/releases/tag/v0.4.3
- 官方使用说明要求每次操作继续使用最新返回的 `stateId`：  
  https://github.com/injaneity/pi-computer-use/blob/v0.4.3/docs/usage.md

## 社区资料

官方仓库当前没有找到针对这一精确报错的公开 issue（问题单）：

- https://github.com/injaneity/pi-computer-use/issues?q=is%3Aissue+%22State+is+stale%22
- https://github.com/injaneity/pi-computer-use/issues?q=is%3Aissue+%22Element+reference+is+stale%22

其他项目的同名错误不属于该实现，未作为证据。

## 使用建议

1. 动作失败后不要复用旧 `stateId`，重新观察；
2. 对窗口根、画布或语义树很浅的应用，使用 `fused`（融合）观察并显式请求图像，再用坐标操作；
3. 普通控件仍优先使用可操作的语义引用，不要把窗口根节点当作输入目标。

## 截图黑屏社区反馈

调查日期：2026-07-26

### 检索范围

- 官方 GitHub 仓库截至调查时公开的 43 条 issue（问题单）/PR（拉取请求）、21 个 release（发布）说明，以及仓库内 discussion（讨论）；该仓库的 Discussions（讨论区）当前未启用：  
  https://github.com/injaneity/pi-computer-use/issues?q=is%3Aissue  
  https://github.com/injaneity/pi-computer-use/pulls?q=is%3Apr  
  https://github.com/injaneity/pi-computer-use/releases  
  https://github.com/injaneity/pi-computer-use/discussions
- 对上述 issue（问题单）/PR（拉取请求）逐词检索：`"black screen"`、`"black screenshot"`、`PrintWindow`、`BitBlt`、`Chromium`、`Electron`、`D3D`、`GPU`、`capture`。代表性可复查查询：  
  https://github.com/injaneity/pi-computer-use/issues?q=is%3Aissue+%22black+screen%22  
  https://github.com/injaneity/pi-computer-use/issues?q=is%3Aissue+PrintWindow  
  https://github.com/injaneity/pi-computer-use/issues?q=is%3Aissue+BitBlt  
  https://github.com/injaneity/pi-computer-use/issues?q=is%3Aissue+%28Chromium+OR+Electron+OR+D3D+OR+GPU%29+capture
- npm（包注册表）和 Pi（编码代理）包页面，以及能明确提到 `@injaneity/pi-computer-use` 或 `injaneity/pi-computer-use` 的公开网页、GitHub 全站结果、Reddit（社区）和可被搜索引擎索引的 Discord（聊天社区）镜像：  
  https://www.npmjs.com/package/@injaneity/pi-computer-use  
  https://pi.dev/packages/%40injaneity/pi-computer-use  
  https://www.answeroverflow.com/m/1496685050467717162

### 结果与归属判断

**没有找到可归属该扩展的公开用户反馈，声称 Windows 下 Chromium（浏览器内核）、Electron（桌面应用框架）或 D3D/GPU（图形加速）窗口被捕获为黑屏，也没有找到“`PrintWindow` 返回黑图但备用 `BitBlt` 未触发”的 issue（问题单）、PR（拉取请求）、discussion（讨论）、release（发布说明）或外部社区报告。** npm（包注册表）和 Pi（编码代理）页面只是软件说明页，没有评论区或相关故障记录；可索引的外部讨论也未出现这些症状。

唯一直接相关的官方内容是 Windows 支持的实现 PR（拉取请求），但它是维护者/贡献者预先记录的**已知限制**，不是用户黑屏报告：PR #16 明确说明 Windows 截图采用 GDI（图形设备接口）的 `PrintWindow`，部分 DirectX（图形接口）/overlay（叠加层）内容可能空白或不完整，并把 DXGI（桌面复制接口）或 Windows Graphics Capture（Windows 图形捕获）升级留待以后。该 PR 的 Windows 11 实机验收评论覆盖 Notepad（记事本）的截图、UIA（界面自动化）、窗口移动和遮挡等流程，记录了菜单与引用问题，但没有报告截图黑屏：  
https://github.com/injaneity/pi-computer-use/pull/16  
https://github.com/injaneity/pi-computer-use/pull/16#issuecomment-4886836134

该 PR 对应提交中的捕获源码只调用 `PrintWindow`，当时还没有 `BitBlt` 备用路径；本机安装的 0.4.3 源码后来已经加入该备用路径。因此，这条历史资料只能证明维护者知道 GDI（图形设备接口）的限制，不能证明社区反馈过当前 0.4.3 的黑屏判断问题：  
https://github.com/injaneity/pi-computer-use/blob/97d98b56eaf6f95d10d5092567e1ecbc16e43566/native/windows/bridge-rs/src/capture.rs

`Electron` 命中的官方 issue #13 讨论的是混合应用的 UIA（界面自动化）语义覆盖，不是截图黑屏；v0.4.2 的发布说明只宣布 Windows 截图支持，也没有黑屏修复或已知问题条目：  
https://github.com/injaneity/pi-computer-use/issues/13  
https://github.com/injaneity/pi-computer-use/releases/tag/v0.4.2

### 一般问题（不归属该扩展）

Windows/Chromium（浏览器内核）生态确有相似的一般问题，例如 Chromium 项目的报告称 `PrintWindow()` 捕获 Aura/Chrome 窗口会得到黑图；Stack Overflow（问答社区）也有其他程序使用 `BitBlt` 后得到黑图的提问。这些资料说明该技术风险真实存在，但均未提及 `@injaneity/pi-computer-use`，不能算作该扩展的社区反馈：  
https://issues.chromium.org/issues/40334080  
https://stackoverflow.com/questions/38868275/screenshot-captured-using-bitblt-in-c-sharp-results-a-black-image-on-windows-10  
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-printwindow

### 结论

截至本次可见公开资料，结论是“**官方已在实现 PR（拉取请求）中预告 GDI（图形设备接口）对 DirectX（图形接口）/叠加内容可能空白，但尚未发现该扩展用户实际提交的 Windows Chromium（浏览器内核）/Electron（桌面应用框架）截图黑屏报告**”。搜索引擎无法覆盖私有 Discord（聊天社区）、未公开聊天和未来新增内容，因此这是否定公开可检索反馈，不是否定问题本身可能存在。
