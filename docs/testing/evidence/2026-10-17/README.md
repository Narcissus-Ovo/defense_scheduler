# 10月17日本地补测证据

实际执行2026-10-17（Asia/Shanghai），QA起点0e4d93d、业务43afaf9，feat/testing。仅使用已核实12名QA学生的10-16合成库一致性副本；原合成库与业务库不变。源预答辩实际发布，正式草稿移动后源预组保持不变。

| 文件 | 内容 |
| --- | --- |
| [student-group-results.json](student-group-results.json) | 真实DRF：2通过、1失败、1部分；列表/详情缺currentGroup，源组可从排期读取 |
| [student-browser-results.json](student-browser-results.json) | 实际Edge真实登录：首屏10名已分组学生均显示未分组；全零权重评分面板0/0通过；JS异常0 |
| [student-current-group.png](student-current-group.png) | 首屏10行“未分组”，总计12学生；对应DEF-E-014 |
| [quality-boundary-results.json](quality-boundary-results.json) | 实际TS评分函数+真实API合成结果+实际Mock生成器，9例8通过1失败；不是精确公式签认或全量Mock浏览器验收 |
| [quality-five-observed.json](quality-five-observed.json) | 五项正权重仍仅三项，DEF-E-005保持开放 |
| [real-schedule.json](real-schedule.json) | 本次评分实际输入；合成正式草稿，移动后有已检出的硬冲突，未声称此草稿可发布 |
| [quality-zero-browser.png](quality-zero-browser.png) | 实际面板0/0、不出现NaN/Infinity；分母0显示本身未被当作最终评分公式签认 |
| [local-check.json](local-check.json) | 源码/旧证据/原库不变，评分输入摘要、现有候选ZIP名单/摘要/完整性再核对 |

SHA256SUMS覆盖全部其他文件；.gitattributes保留原字节。本目录无DB/账号密码/Token/运行密钥/二进制包。浏览器临时凭据与日志仅在忽略的.tmp目录；服务与浏览器均已清理。旧optimizationMock固定分观察仅为非活跃代码风险，页面两种模式实际共用optimization.ts，没有另计独立在用缺陷。

复跑先确保10-16合成库存在；新机器可执行scripts/qa/acceptance-cycle.py生成（会替换其.tmp内合成结果，不改归档证据）。随后执行scripts/qa/student-group-contract.py、Node运行quality-boundaries.cjs。student-group-browser.cjs需要Node可require Playwright、已安装Edge，会自动使用副本启动服务；不需要手动启动业务环境。诊断退出0表示采集完成，是否通过看各status。
