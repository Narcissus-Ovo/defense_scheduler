# TASK-P06 正式专家随机补充 - 验证说明

## 验证范围

验证正式答辩排期对专家的自动补充、软件学院专家主体规则、专家参与次数均衡，以及随机种子的可复现性。随机补充仅在满足资格、可用时间和其他硬规则的候选人中进行。

## 自动化验证

在项目根目录执行：

```powershell
python manage.py test api.test_architecture_v2.SchedulePolicyBoundaryTests.test_formal_random_balance_is_enabled_by_default_but_can_be_disabled api.test_algorithm_v2.CommitteeV2Tests.test_formal_requires_software_college_majority api.test_algorithm_v2.CommitteeV2Tests.test_generation_prefers_software_college_reviewers api.test_algorithm_v2.SchedulingPreferencesV2Tests.test_software_reviewers_rotate_with_at_most_one_count_difference api.test_algorithm_v2.SchedulingPreferencesV2Tests.test_random_seed_changes_equal_load_reviewer_selection_reproducibly api.test_architecture_v2.ArchitectureV2IntegrationTests.test_generation_persists_explicit_random_seed_in_rule_snapshot
```

预期：测试通过。验证正式答辩专家配置及软件学院专家占主体、参与次数均衡、相同种子生成结果一致，以及显式种子保存在版本规则快照中。

## 手工验证步骤

1. 准备足够数量且资格、可参加答辩类型、可用时间均符合要求的教师，并维护软件学院导师标记。
2. 配置正式答辩规则，使用相同数据连续生成两次排期。
   - 验证每组专家人数符合正式答辩规则（主席计入专家人数）。
   - 验证软件学院专家占主体；候选人满足硬规则时，系统优先补充软件学院专家。
   - 验证多组之间的软件学院专家参与次数尽量均衡，不会无故集中分配给少数教师。
3. 使用相同的 `random_seed` 再次生成。
   - 验证同一输入与种子得到相同的人员分配。
4. 更换种子后再次生成。
   - 验证在同等可行候选人之间允许产生不同选择，同时专家资格、可用时间和人数等硬约束仍满足。
5. 将软件学院参与均衡权重设为 0 后生成。
   - 验证不再执行该软均衡偏好，硬性人数与资格校验仍然生效。

## 相关边界

- 随机性用于同等可行候选人的选择，不得覆盖资格、时间、回避或专家人数等硬约束。
- 资源不足时应如实呈现冲突或缺口，不应通过重复安排同一教师伪造满足条件的结果。
- 正式答辩未显式提供种子时由系统生成并记录种子；其他答辩类型不应因此产生无意义的随机种子。
