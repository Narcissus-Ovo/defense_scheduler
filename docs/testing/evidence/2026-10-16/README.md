# 2026-10-16 实测证据

计划日为10-14、15、16，实际执行均为2026-10-16（Asia/Shanghai）。业务基线43afaf9；QA起点a426761；分支feat/testing。全部数据为合成数据。这里只复制明确白名单内的结果、文件和截图；不包含数据库、账号凭据、Token、运行密钥或EXE。

| 文件 | 解释 |
| --- | --- |
| [baseline-report.json](baseline-report.json) / [backend-cases.json](backend-cases.json) | lint/domain/types/build/Django/迁移检查通过；后端243项中241通过、2跳过。第二次运行专为采集逐测试ID，不与第一次相加 |
| [daily-results.json](daily-results.json) | 46规则案例：26通过、17失败、3阻塞；采集命令退出0不代表规则全部通过 |
| [api-results.json](api-results.json) | 14个实际服务案例均通过，含三类×两校区六组合、生命周期、移动、调整、数据、日期、冲突和导出 |
| [browser-results.json](browser-results.json) / [theme-results.json](theme-results.json) | Playwright 1.62.1 + Edge155真实HTTP、生产前端、无route mock；14案例11通过3失败，页面JS异常0 |
| [quality-probe.json](quality-probe.json) | 当日真实前端评分函数，五项正权重仍仅三项；不代替公式签认 |
| [color-results.json](color-results.json) | 实际已发布17组102学生导出，17导师仅11色；Excel/Word同导师一致 |
| [migration-results.json](migration-results.json) | 空库、合成0008副本升级、校验备份并恢复到新路径；非真实业务库升级或旧EXE回退 |
| [exe-results.json](exe-results.json) / [package-results.json](package-results.json) | 实际EXE启动、接口、导出和完整性冒烟；QA候选包白名单/哈希；不是新业务规则验收通过 |
| [office-render.json](office-render.json) | Office16只读打开实际导出文件后转PDF，记录输入摘要，没有保存回源文件 |
| [delivery-check.json](delivery-check.json) | 42行及分类数、四组测试计数、导出与Office输入摘要、包内名单/EXE摘要、旧证据及业务源码不变的最后核对；不代表产品验收通过 |
| [final-contact.png](final-contact.png) | PDF四页、Excel典型页面与Word对照；可结合原PDF复核 |

pre/formal/mid 的 A/B分别为创新港/兴庆。正常样例12学生；17导师压力样例102学生。history-long.pdf为浏览器导出；*-excel.pdf与*-word.pdf为Office默认打印结果。Word当前不含学生备注，备注硬验收重点按需求覆盖Excel/PDF，未擅自扩大Word范围。

SHA256SUMS.txt覆盖本目录所有其他文件（含本说明），不对自身计算。本目录.gitattributes禁用文本换行转换，确保提交与检出后的证据摘要一致；合成XLSX单独加入版本控制。截图只保留最终有效流程和缺陷图，未复制早期测试脚本修正时留下的无效失败图。原始日志保留本机.tmp，业务库未写入。
