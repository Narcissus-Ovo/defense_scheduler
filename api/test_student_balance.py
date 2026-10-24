"""The configured target is preferred inside the permitted student range."""
from django.test import SimpleTestCase

from algorithm import build_student_groups, parse_student, parse_teacher
from scheduling.balance import balance_student_groups


class StudentBalanceTests(SimpleTestCase):
    def batches(self, mentors):
        offset = 0
        batches = []
        for ids in mentors:
            batches.append([parse_student({'id': offset + i + 1, 'supervisor_id': tid,
                                           'campus': '创新港'}) for i, tid in enumerate(ids)])
            offset += len(ids)
        return batches

    def test_seven_and_five_become_two_target_six_groups(self):
        batches = self.batches([[1, 1, 2, 3, 4, 5, 6], [7, 7, 8, 9, 10]])
        original = sorted(s.id for b in batches for s in b)
        balance_student_groups(batches, 6, 5, 7, lambda s: True, lambda b: True)
        self.assertEqual([len(b) for b in batches], [6, 6])
        self.assertEqual(sorted(s.id for b in batches for s in b), original)

    def test_balance_keeps_external_students_chairs_and_four_mentors(self):
        batches = self.batches([[9, 9, 9, 1, 1, 2, 3], [10, 10, 4, 5, 6]])
        external_before = [[s.id for s in b if s.supervisor_id in {9, 10}] for b in batches]

        def valid(batch):
            mentors = {s.supervisor_id for s in batch}
            return len(mentors) >= 4 and bool(mentors & {1, 4})

        balance_student_groups(batches, 6, 5, 7, lambda s: s.supervisor_id not in {9, 10}, valid)
        self.assertEqual([len(b) for b in batches], [6, 6])
        self.assertTrue(all(valid(b) for b in batches))
        self.assertEqual([[s.id for s in b if s.supervisor_id in {9, 10}] for b in batches], external_before)

    def test_balance_does_not_cross_campuses_or_break_a_required_mentor(self):
        for reason in ('campus', 'mentor'):
            with self.subTest(reason=reason):
                batches = self.batches([[1, 2, 3, 4, 5, 6, 7], [8, 8, 9, 10, 11]])
                if reason == 'campus':
                    for s in batches[1]:
                        s.campus = '兴庆'
                before = [[s.id for s in b] for b in batches]
                balance_student_groups(batches, 6, 5, 7, lambda s: True,
                                       lambda b: not any(s.supervisor_id == 1 for s in b) or len(b) == 7)
                self.assertEqual([[s.id for s in b] for b in batches], before)

    def test_formal_independent_groups_also_prefer_the_target(self):
        students = [s for b in self.batches([[1] * 7, [2] * 5]) for s in b]
        rules = {'policy_version': 2, 'defense_type': 'formal', 'group_size': 6,
                 'group_min': 5, 'group_max': 7, 'grouping': 'supervisor', 'supervisor_policy': 'avoid'}
        batches = build_student_groups(students, rules, set(), [parse_teacher({'id': i}) for i in (1, 2)])
        self.assertEqual(sorted(map(len, batches)), [6, 6])

    def test_three_group_transfer_balances_without_creating_an_external_visit(self):
        batches = self.batches([[9, 9, 9, 9, 1, 2, 3], [9, 9, 4, 5, 6, 7], [10, 10, 8, 11, 12]])
        external_before = [{s.supervisor_id for s in b if s.supervisor_id in {9, 10}} for b in batches]

        def valid(batch):
            mentors = {s.supervisor_id for s in batch}
            return len(mentors) >= 4 and bool(mentors & {1, 4, 8})

        def allowed(before, after):
            return all({s.supervisor_id for s in a if s.supervisor_id in {9, 10}}
                       == {s.supervisor_id for s in b if s.supervisor_id in {9, 10}}
                       for a, b in zip(before, after))

        balance_student_groups(batches, 6, 5, 7, lambda s: True, valid, allowed)
        self.assertEqual(list(map(len, batches)), [6, 6, 6])
        self.assertTrue(all(valid(b) for b in batches))
        self.assertEqual([{s.supervisor_id for s in b if s.supervisor_id in {9, 10}} for b in batches], external_before)
        self.assertEqual(sorted(s.id for b in batches for s in b), list(range(1, 19)))

    def test_low_balance_weight_keeps_the_explicit_compact_preference(self):
        students = [s for b in self.batches([[1] * 7, [2] * 5]) for s in b]
        rules = {'policy_version': 2, 'defense_type': 'formal', 'group_size': 6,
                 'group_min': 5, 'group_max': 7, 'grouping': 'supervisor', 'supervisor_policy': 'avoid',
                 'soft_weights': {'balance_student_count': 20}}
        batches = build_student_groups(students, rules)
        self.assertEqual(sorted(map(len, batches)), [5, 7])

    def test_formal_inherited_groups_are_kept_intact(self):
        batches = self.batches([[1] * 7, [2] * 5])
        for i, batch in enumerate(batches):
            for student in batch:
                student.previous_group_id = f'G{i + 1}'
        rules = {'policy_version': 2, 'defense_type': 'formal', 'group_size': 6,
                 'group_min': 5, 'group_max': 7, 'grouping': 'secretary'}
        inherited = build_student_groups([s for b in batches for s in b], rules)
        self.assertEqual([[s.id for s in b] for b in inherited], [[s.id for s in b] for b in batches])
