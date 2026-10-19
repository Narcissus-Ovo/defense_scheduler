"""Synthetic checks for interactions between the October integration branches."""
from datetime import datetime

from django.test import SimpleTestCase

from algorithm import (
    GroupDraft, TimeRange, detect_global_conflicts, generate_schedule,
    parse_room, parse_student, parse_teacher,
)


class IntegratedSupervisorChecks(SimpleTestCase):
    def test_idempotent_retry_allows_generated_seed_but_rejects_changed_explicit_seed(self):
        from .schedule_views import ScheduleViewSet

        requested = {'defense_type': 'formal', 'expert_count': 5}
        saved = {**requested, 'random_seed': 41}
        self.assertTrue(ScheduleViewSet._rules_equivalent(saved, requested))
        self.assertTrue(ScheduleViewSet._rules_equivalent(saved, {**requested, 'random_seed': 41}))
        self.assertFalse(ScheduleViewSet._rules_equivalent(saved, {**requested, 'random_seed': 42}))

    def test_every_group_checks_its_mentor_without_external_teachers(self):
        teachers = [parse_teacher({
            'id': number, 'name': f'合成教师{number}', 'title': '教授',
        }) for number in range(1, 9)]
        students = [parse_student({
            'id': number, 'name': f'合成学生{number}', 'supervisor_id': number + 6,
        }) for number in (1, 2)]
        drafts = [GroupDraft(
            f'G{number}', None, [number],
            TimeRange(datetime(2031, 7, 14 + number, 9), datetime(2031, 7, 14 + number, 12)),
            1, 1, [2, 3, 4, 5], 6,
        ) for number in (1, 2)]
        conflicts = detect_global_conflicts(
            drafts, students, teachers, [parse_room({'id': 1, 'capacity': 20})],
            {'defense_type': 'pre', 'policy_version': 2, 'supervisor_policy': 'same_group',
             'expert_count': 5, 'expert_min': 5, 'need_chair': True,
             'expert_count_includes_chair': True},
        )
        missing = [item for item in conflicts if item['type'] == 'supervisor_missing']
        self.assertEqual(len(missing), 2, conflicts)
        self.assertEqual({item['related_ids'][0] for item in missing}, {'G1', 'G2'})

    def test_formal_internal_chair_priority_uses_external_flag_not_college(self):
        teachers = [
            {'id': 1, 'name': '校内正高', 'title': '教授', 'college': '其他学院',
             'is_external': False, 'roles': ['主席', '普通专家']},
            *[{'id': number, 'name': f'软件专家{number}', 'title': '副教授',
               'college': '软件学院', 'roles': ['普通专家']}
              for number in (2, 3, 4)],
            {'id': 5, 'name': '外院正高', 'title': '教授', 'college': '外院',
             'is_external': True, 'roles': ['主席', '普通专家']},
            {'id': 6, 'name': '指定秘书', 'title': '助理教授', 'roles': ['秘书']},
        ]
        result = generate_schedule(
            teachers, [{'id': 1, 'name': '合成学生', 'campus': '创新港'}],
            [{'id': 1, 'campus': '创新港', 'capacity': 30}],
            {'defense_type': 'formal', 'policy_version': 2,
             'start_date': '2031-07-14', 'end_date': '2031-07-14',
             'group_size': 1, 'group_min': 1, 'group_max': 1,
             'expert_count': 5, 'expert_min': 5, 'need_chair': True,
             'expert_count_includes_chair': True, 'chair_title': '教授',
             'secretary_title': '讲师', 'supervisor_policy': 'avoid', 'random_seed': 42},
        )
        self.assertEqual(result['groups'][0]['chair_id'], 1, result)
        self.assertEqual(result['conflicts'], [])

    def test_all_day_booking_is_split_before_assigning_a_group(self):
        result = generate_schedule(
            [{'id': number, 'name': f'合成专家{number}', 'title': '教授'}
             for number in range(1, 7)],
            [{'id': 1, 'name': '合成学生', 'supervisor_id': 1}],
            [{'id': 1, 'capacity': 30,
              'available_time': ['2031-07-14 08:50-18:10']}],
            {'defense_type': 'pre', 'policy_version': 2,
             'start_date': '2031-07-14', 'end_date': '2031-07-14',
             'group_size': 1, 'group_min': 1, 'group_max': 1,
             'expert_count': 5, 'expert_min': 5, 'need_chair': True,
             'expert_count_includes_chair': True, 'chair_title': '教授',
             'secretary_title': '讲师', 'supervisor_policy': 'same_group'},
        )
        self.assertEqual(result['groups'][0]['time'], '2031-07-14 09:00-12:00')
        self.assertEqual(result['conflicts'], [])
