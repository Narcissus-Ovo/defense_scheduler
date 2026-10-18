# TASK-P07 导师资料预检 - 验证说明

## 验证范围

验证排期前能够检查学生导师资料是否缺失、无法匹配教师记录、已停用或不适用于当前答辩类型；预检失败时，生成操作不得创建排期版本。

## 自动化验证

在项目根目录执行：

```powershell
python manage.py test api.test_architecture_v2.ArchitectureV2IntegrationTests.test_generation_and_linked_generation_block_missing_mentor_data api.test_architecture_v2.ArchitectureV2IntegrationTests.test_preflight_blocks_inactive_or_filtered_mentor_without_creating_a_version
```

预期：测试通过。覆盖导师缺失、导师姓名无法匹配、教师未配置当前答辩类型及教师停用等情况，并检查单独生成和联合生成不会在预检失败后创建版本。

## 手工验证步骤

分别准备以下学生／教师数据，并在排期向导中执行预检：

1. 学生没有导师关联及导师姓名。
   - 验证预检报告 `mentor_missing`，列出受影响学生。
2. 学生保留导师姓名，但教师资料中找不到匹配教师。
   - 验证预检报告 `mentor_not_found`，指出无法匹配的导师姓名。
3. 导师教师记录已停用，或未将当前答辩类型加入可参加类型。
   - 验证预检报告 `mentor_unavailable_for_defense`，列出学生与导师。
4. 对以上任一错误数据继续尝试单阶段生成，以及预答辩／正式答辩联合生成。
   - 验证生成被拒绝并提示预检未通过。
   - 验证数据库中没有因此新增排期版本，原有学生关系及版本不变。
5. 修复导师资料后重新预检并生成。
   - 验证错误消失，生成流程可继续；不相关的数据质量提示仍应保留并正确显示。

## 相关边界

- 预检接口返回诊断结果；对于阻止生成的错误，正式生成接口也必须再次拦截，不能只依赖前端预检按钮。
- 预检失败不应创建空版本或部分版本，也不应静默替换缺失导师。
