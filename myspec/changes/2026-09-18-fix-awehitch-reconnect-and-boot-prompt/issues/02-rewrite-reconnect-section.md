# 02 — 重新连接那节按实测链路重写

**What to build:** 技能里「reconnect after address reclaim」那一节现在把触发条件挂在两个**不会亮**的标志位上，Agent（代理）照它走会卡死；而且它漏了唯一真正重建连接的那一步。本票据把这一节改成按实测走通的三步：**先试一次最小往返 → 报出本工作区名即为连上 → 不通就跑 `connector-setup` 再回到第一步**。同时删掉不成立的 doctor 门禁，并把登录表述更正为异常路径。

**Blocked by:** 01（共用同一个补丁脚本与同一个测试文件，写入必须串行）

**Status:** ready-for-agent

- [ ] 渲染后的技能文本里，那一节含**三步**：① 试一次最小 `[C2C]` 往返 → ② 回复报出本工作区名即为已连上 → ③ 不通则跑 `awehitch connector-setup -w <仓库>`，然后回到第 ① 步。
- [ ] 该节**不再引用**那两个标志位（`chatgptSetup.needed` / `chatgptRepair.needed`）。
- [ ] 同一模板里**另一处**引用同一套标志的地方（doctor 门禁那段）**已同步修改**，两处不再自相矛盾。
- [ ] 「本地不全绿就不开 ChatGPT」的 **doctor 门禁已删除**。
- [ ] 登录表述更正为**异常路径**：默认全自动，只有返回 `needsLogin` 时才需要人登录一次。
- [ ] 改写的**理由准确**：不写成「重启场景里永不亮」，而是「bridge 状态为『状态不明』时永不点亮；为『已停止』时会点亮，但只在一次运行的窗口内有效」。
- [ ] 红灯证据与绿灯证据来自**同一入口**（渲染后的技能文本）。
- [ ] 改动以本地补丁形式进入 `scripts/awehitch-local-patches.ps1`。
- [ ] 一个提交。

**Spec reference:** `myspec/changes/2026-09-18-fix-awehitch-reconnect-and-boot-prompt/spec.md`
