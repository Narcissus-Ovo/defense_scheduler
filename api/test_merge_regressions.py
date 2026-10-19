"""Synthetic checks for interactions between the October integration branches."""
from datetime import datetime

from django.test import SimpleTestCase

from algorithm import (
    GroupDraft, TimeRange, detect_global_conflicts,
    parse_room, parse_student, parse_teacher,
)


class IntegratedSupervisorChecks(SimpleTestCase):
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
