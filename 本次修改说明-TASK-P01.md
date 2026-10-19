# 本次修改说明（任务包一）

本文件对应本次工作区中的 TASK-P02、P04、P05、P09、P12 改动。源码和文档中的 `TASK-Pxx 新增/修改/测试` 注释用于定位改动块；注释仅作追踪，不参与运行逻辑。

## TASK-P02：答辩类型与基础数据导航

- [src/components/AppSidebar.vue](src/components/AppSidebar.vue)：新增答辩类型选择；导航调整为工作台、安排要求、分组与发布，并独立列出基础数据入口。切换类型沿用路由 `type` 查询参数。
- 验证：前端类型检查通过；390px 窄屏检查未出现页面横向溢出。

## TASK-P04：专家人数与职称资格

- [shared/defense-policy.json](shared/defense-policy.json)：预答辩固定为 5 位专家，含 1 位组长及 4 位普通专家。
- [api/serializers.py](api/serializers.py)、[api/services/rules.py](api/services/rules.py)、[src/utils/wizardValidation.ts](src/utils/wizardValidation.ts)、[src/components/RuleConfigForm.vue](src/components/RuleConfigForm.vue)：同步校验和界面人数口径。
- [scheduling/policies.py](scheduling/policies.py)、[algorithm.py](algorithm.py)、[src/domain/defense.ts](src/domain/defense.ts)、[src/types/teacher.ts](src/types/teacher.ts)、[src/types/schedule.ts](src/types/schedule.ts)、[src/views/teacher/TeacherList.vue](src/views/teacher/TeacherList.vue)：统一教授/研究员及副教授/副研究员职称等级和维护选项。
- [api/migrations/0010_pre_committee_headcount.py](api/migrations/0010_pre_committee_headcount.py)：把现有预答辩配置迁移为固定 5 位。

## TASK-P05：外院导师组数与冲突

- [algorithm.py](algorithm.py)：外院导师少于 3 名学生时保持一组，3 名及以上拆为两组；生成与全局重验检查实际组数。
- [api/schedule_views.py](api/schedule_views.py)：外院导师组数冲突映射为错误级，错误草稿不能发布。
- [api/test_algorithm_v2.py](api/test_algorithm_v2.py)：覆盖 2/3/4 人、跨校区和组人数下限等场景。

## TASK-P09：五项排期评分

- [src/utils/optimization.ts](src/utils/optimization.ts)：按实际结果计算人数均衡、正高优先、跨校区、外院导师集中和学硕优先五项评分；缺少数据时单列未评估，不计入分母。
- [src/utils/optimizationMock.ts](src/utils/optimizationMock.ts)：改为复用真实评分口径。
- [src/types/optimization.ts](src/types/optimization.ts)、[src/components/SoftConstraintPanel.vue](src/components/SoftConstraintPanel.vue)：增加权重和未评估原因展示。软件学院评审次数均等不进入总分。
- [api/schedule_views.py](api/schedule_views.py)、[src/types/schedule.ts](src/types/schedule.ts)：排期响应提供导师外院标记及版本规则快照。
- [scripts/test-frontend-domain.cjs](scripts/test-frontend-domain.cjs)：覆盖五项评分、缺失数据及演示/真实口径一致性。

## TASK-P12：版本化导出

- [api/export_word.py](api/export_word.py)：Word 增加学生名单与导师/秘书关系、备注开关和冲突标记。
- [api/schedule_views.py](api/schedule_views.py)：Word 导出使用选中版本的备注配置及冲突数据。
- [src/api/export.ts](src/api/export.ts)、[src/types/schedule.ts](src/types/schedule.ts)：PDF 备注配置优先读取所选版本快照。
- [api/test_algorithm_v2.py](api/test_algorithm_v2.py)：覆盖 Word 关系内容、备注开关、错误标红及版本响应字段。

## 其他同步

- [docs/requirements/README.md](docs/requirements/README.md)、[docs/requirements/全量需求追踪.md](docs/requirements/全量需求追踪.md)：记录 2026-10-12 确认的预答辩人数与评分范围，并保留此前决定的历史。
- [产品体验与待办清单-2026-10-12.md](产品体验与待办清单-2026-10-12.md)：包含 P02-P12 的任务拆分建议。
- [api/test_data_v2.py](api/test_data_v2.py)、[api/tests.py](api/tests.py)：更新配置迁移、默认规则及 API 契约测试。

## 无法行内标记的文件

- [shared/defense-policy.json](shared/defense-policy.json) 是标准 JSON，不支持注释；对应的预答辩专家人数键已在 TASK-P04 中说明。
- [tests/fixtures/批量测试_学生_100人.xlsx](tests/fixtures/批量测试_学生_100人.xlsx) 是二进制 Excel，无法插入文本标记；请通过版本控制差异单独审阅其内容。

## 验证记录

- Django 全量测试：253 项通过，2 项跳过。
- 前端：`npm run test:domain`、`npm run lint`、`npm run build` 通过。
- 迁移与差异：`manage.py makemigrations --check --dry-run` 无未生成迁移；`git diff --check` 通过。