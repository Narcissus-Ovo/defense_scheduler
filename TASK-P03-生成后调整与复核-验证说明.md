# TASK-P03 生成后调整与复核 - 验证说明

## 验证范围

验证生成排期后进行学生移动、分组或时间调整时，关联关系能够正确保留，冲突检查能够反映调整后的实际排期，并阻止带有硬冲突的草稿发布。

## 自动化验证

在项目根目录执行：

```powershell
python manage.py test api.test_architecture_v2.ArchitectureV2IntegrationTests.test_move_keeps_secretary_and_moves_mentor_then_rechecks_conflicts api.test_architecture_v2.ArchitectureV2IntegrationTests.test_fully_occupied_course_halves_cannot_be_published api.test_architecture_v2.ArchitectureV2IntegrationTests.test_adjust_group_rejects_mismatched_teacher_id_without_mutation
```

预期：测试通过。覆盖移动学生时保留秘书绑定、同步导师并重验冲突；硬冲突草稿不能发布；无效人员信息被拒绝且不会改写原排期。

## 手工验证步骤

1. 进入排期结果页，生成一个草稿并记录版本号。
2. 将学生从源组移动到目标组，保持默认秘书关系。
   - 验证目标组学生名单包含该学生，导师关系随学生迁移。
   - 验证目标组原有秘书关系未被覆盖；秘书绑定仍跟随学生，除非明确选择改绑。
   - 验证操作完成后冲突面板刷新，显示的是调整后的排期结果。
3. 修改组别人员或时间后再次检查冲突。
   - 验证不匹配的教师 ID／姓名等无效数据会被拒绝，原排期不发生部分修改。
   - 验证冲突检查结果与当前版本展示的冲突一致。
4. 准备一个存在硬冲突的草稿并尝试发布。
   - 验证发布被拒绝，草稿仍保持草稿状态，界面展示冲突信息。
5. 查看操作日志。
   - 验证移动或调整记录关联到正确的排期版本，并包含操作内容及调整后的版本修订信息。

## 相关边界

- 秘书关系默认随学生保留；只有管理员明确改绑时才更新学生秘书绑定。
- 调整后的软提示不等同于硬冲突；发布拦截应针对阻止发布的冲突。
- 验证发布拦截时应使用草稿版本，避免影响已有正式发布版本。
