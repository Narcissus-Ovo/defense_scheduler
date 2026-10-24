"""Pre-defense reviewers must be exactly the mentors of that group's students."""
from datetime import datetime

from django.test import SimpleTestCase

from algorithm import (
    GroupDraft, TimeRange, detect_global_conflicts, generate_schedule,
    parse_room, parse_student, parse_teacher,
)


class PreMentorCommitteeTests(SimpleTestCase):
    def teachers(self):
        return [
            {'id': 1, 'name': '组内导师组长', 'title': '教授', 'roles': ['组长', '普通专家']},
            {'id': 2, 'name': '组内导师甲', 'title': '副教授', 'roles': ['普通专家']},
            {'id': 3, 'name': '组内导师乙', 'title': '副教授', 'roles': ['普通专家']},
            {'id': 4, 'name': '指定秘书', 'title': '讲师', 'roles': ['秘书']},
            {'id': 5, 'name': '无本组学生专家', 'title': '教授', 'roles': ['组长', '普通专家']},
            {'id': 6, 'name': '额外专家', 'title': '教授', 'roles': ['普通专家']},
            {'id': 7, 'name': '组内导师丙', 'title': '副教授', 'roles': ['普通专家']},
        ]

    def students(self):
        return [{'id': i, 'name': f'学生{i}', 'supervisor_id': i} for i in (1, 2, 3, 7)]

    def rules(self):
        return {
            'defense_type': 'pre', 'policy_version': 2,
            'start_date': '2026-04-01', 'end_date': '2026-04-01',
            'group_size': 4, 'group_min': 3, 'group_max': 6,
            'expert_count': 4, 'expert_min': 4, 'expert_count_includes_chair': True,
            'need_chair': True, 'chair_title': '副教授', 'secretary_title': '讲师',
            'supervisor_policy': 'same_group', 'grouping': 'supervisor',
        }

    def check(self, chair, experts):
        draft = GroupDraft('G1', None, [1, 2, 3, 7],
                           TimeRange(datetime(2026, 4, 1, 9), datetime(2026, 4, 1, 12)),
                           1, chair, experts, 4)
        return detect_global_conflicts(
            [draft], list(map(parse_student, self.students())),
            list(map(parse_teacher, self.teachers())), [parse_room({'id': 1, 'capacity': 30})],
            self.rules(),
        )

    def test_manual_review_reports_expert_without_own_student(self):
        conflicts = self.check(1, [2, 3, 7, 5, 6])
        missing = [c for c in conflicts if c['type'] == 'pre_reviewer_without_student']
        self.assertEqual({c['teacher_name'] for c in missing}, {'无本组学生专家', '额外专家'})

    def test_manual_review_also_checks_the_chair(self):
        conflicts = self.check(5, [1, 2, 3, 7, 6])
        missing = [c for c in conflicts if c['type'] == 'pre_reviewer_without_student']
        self.assertIn('无本组学生专家', {c['teacher_name'] for c in missing})

    def test_generation_never_pads_committee_with_unrelated_reviewers(self):
        result = generate_schedule(self.teachers(), self.students(), [{'id': 1, 'capacity': 30}], self.rules())
        group = result['groups'][0]
        self.assertEqual({group['chair_id'], *group['expert_ids']} - {None}, {1, 2, 3, 7})
        self.assertEqual(result['conflicts'], [])

    def test_required_mentors_can_exceed_the_minimum(self):
        students = self.students() + [{'id': 5, 'name': '学生5', 'supervisor_id': 5}]
        result = generate_schedule(self.teachers(), students, [{'id': 1, 'capacity': 30}], self.rules())
        group = result['groups'][0]
        self.assertEqual({group['chair_id'], *group['expert_ids']} - {None}, {1, 2, 3, 5, 7})
        self.assertEqual(result['conflicts'], [])

    def test_raised_minimum_controls_generation_without_unrelated_padding(self):
        rules = {**self.rules(), 'expert_count': 5, 'expert_min': 5}
        insufficient = generate_schedule(self.teachers(), self.students(), [{'id': 1, 'capacity': 30}], rules)
        self.assertIn('expert_count_out_of_range', {c['type'] for c in insufficient['conflicts']})
        enough = generate_schedule(self.teachers(), self.students()+[{'id':5, 'supervisor_id':5}],
                                   [{'id':1, 'capacity':30}], rules)
        self.assertEqual(enough['conflicts'], [])
        self.assertEqual(len({enough['groups'][0]['chair_id'], *enough['groups'][0]['expert_ids']}), 5)

    def test_three_mentors_are_a_hard_conflict_without_padding(self):
        result = generate_schedule(self.teachers(), self.students()[:3], [{'id': 1, 'capacity': 30}], self.rules())
        self.assertEqual({result['groups'][0]['chair_id'], *result['groups'][0]['expert_ids']}, {1, 2, 3})
        self.assertIn('expert_count_out_of_range', {c['type'] for c in result['conflicts']})

    def test_generation_does_not_borrow_an_unrelated_chair(self):
        teachers = self.teachers()
        teachers[0]['roles'] = ['普通专家']
        result = generate_schedule(teachers, self.students(), [{'id': 1, 'capacity': 30}], self.rules())
        self.assertIsNone(result['groups'][0]['chair_id'])
        self.assertIn('chair_unavailable', {c['type'] for c in result['conflicts']})

    def test_regrouping_moves_a_student_to_supply_the_fourth_mentor(self):
        from scheduling.joint_groups import _redistribute_internal_mentors
        mentors = [[1, 1, 3, 4], [2, 5, 6, 7, 8]]
        batches = []
        next_id = 1
        for group in mentors:
            batches.append([parse_student({'id': next_id+i, 'supervisor_id': tid, 'campus': '创新港'})
                            for i, tid in enumerate(group)])
            next_id += len(group)
        self.assertTrue(_redistribute_internal_mentors(batches, {1,2,3,4,5,6,7,8}, {1,2}, 4, 4, 8, lambda batch: True))
        self.assertEqual(sorted(s.id for batch in batches for s in batch), list(range(1, 10)))
        self.assertTrue(all(len({s.supervisor_id for s in batch}) >= 4 for batch in batches))
        self.assertTrue(all(4 <= len(batch) <= 8 for batch in batches))

    def test_regrouping_can_share_a_chairs_students_and_preserve_both_chairs(self):
        from scheduling.joint_groups import _redistribute_internal_mentors
        students = [parse_student({'id': i+1, 'supervisor_id': tid, 'campus': '兴庆'})
                    for i,tid in enumerate([1,1,3,4,2,2,5,6,7])]
        batches = [students[:4], students[4:]]
        self.assertTrue(_redistribute_internal_mentors(batches, set(range(1,8)), {1,2}, 4, 4, 8, lambda batch: True))
        self.assertTrue(all(len({s.supervisor_id for s in batch}) == 4 for batch in batches))
        self.assertTrue(all(any(s.supervisor_id in {1,2} for s in batch) for batch in batches))
