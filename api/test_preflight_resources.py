"""Fast resource checks are warnings; immutable inherited size conflicts block."""
from django.test import SimpleTestCase

from scheduling.preflight import inherited_group_size_issues, resource_availability_issues


class PreflightResourceTests(SimpleTestCase):
    def setUp(self):
        self.rules = {'policy_version': 2, 'defense_type': 'pre',
                      'start_date': '2026-04-01', 'end_date': '2026-04-01',
                      'group_size': 6, 'group_min': 5, 'group_max': 7,
                      'expert_count': 4, 'expert_min': 4, 'expert_count_includes_chair': True,
                      'need_chair': True, 'chair_title': '副教授', 'secretary_title': '讲师'}
        self.payload = {
            'teachers': [{'id': i, 'name': f'T{i}', 'title': '教授',
                          'roles': ['组长', '普通专家'] if i == 1 else ['普通专家']}
                         for i in range(1, 5)] + [
                         {'id': 5, 'name': 'S', 'title': '工程师', 'roles': ['秘书']}],
            'students': [{'id': i, 'name': f'学生{i}', 'supervisor_id': min(i, 4), 'campus': '创新港'}
                         for i in range(1, 7)],
            'rooms': [{'id': 1, 'name': 'R1', 'campus': '创新港', 'capacity': 30}],
        }

    def types(self):
        return {item['type'] for item in resource_availability_issues(self.payload, self.rules)}

    def test_available_resources_do_not_warn(self):
        self.assertEqual(self.types(), set())

    def test_chair_qualification_and_designated_secretary_are_checked(self):
        self.payload['teachers'][0]['title'] = '讲师'
        self.assertIn('chair_availability', self.types())
        self.assertNotIn('secretary_availability', self.types())
        self.payload['teachers'][-1]['is_active'] = False
        self.assertIn('secretary_availability', self.types())

    def test_missing_rooms_allow_a_personnel_draft_with_a_warning(self):
        self.payload['rooms'] = []
        issues = resource_availability_issues(self.payload, self.rules)
        self.assertIn('room_availability', {i['type'] for i in issues})
        self.assertTrue(all(i['level'] == 'warning' for i in issues))

    def test_room_capacity_includes_students_reviewers_and_secretary(self):
        self.payload['rooms'][0]['capacity'] = 9
        self.assertIn('room_availability', self.types())
        self.payload['rooms'][0]['capacity'] = 10
        self.assertNotIn('room_availability', self.types())

    def test_chair_and_secretary_with_disjoint_half_days_warn(self):
        self.payload['teachers'][0]['available_time'] = ['2026-04-01 12:00-23:59']
        self.payload['teachers'][-1]['available_time'] = ['2026-04-01 00:00-12:00']
        self.assertIn('common_availability', self.types())

    def test_an_alternative_common_session_avoids_the_warning(self):
        self.payload['teachers'][0]['available_time'] = ['2026-04-01 09:00-12:00']
        self.assertNotIn('common_availability', self.types())

    def test_common_check_identifies_a_required_mentor_with_no_available_half_day(self):
        self.payload['teachers'][1]['available_time'] = ['2026-04-01 00:00-23:59']
        issues = resource_availability_issues(self.payload, self.rules)
        issue = next(i for i in issues if i['type'] == 'common_availability')
        self.assertIn('T2', issue['teacherNames'])
        self.assertEqual(issue['level'], 'warning')

    def test_same_person_cannot_supply_both_chair_and_secretary(self):
        self.payload['teachers'][0]['roles'].append('秘书')
        self.payload['teachers'].pop()
        self.assertIn('common_availability', self.types())

    def test_inherited_groups_report_both_small_and_large_groups(self):
        self.rules.update(defense_type='formal', preserve_pre_defense_groups=True, group_max=6)
        self.payload['students'] = [dict(id=i, name=f'学生{i}', previous_group_id='G1' if i <= 7 else 'G2')
                                    for i in range(1, 12)]
        issues = inherited_group_size_issues(self.payload, self.rules)
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(i['level'] == 'error' for i in issues))
        self.assertIn('G1', issues[0]['description'])
        self.assertIn('7 人', issues[0]['description'])
        self.assertIn('G2', issues[1]['description'])
        self.assertIn('4 人', issues[1]['description'])

    def test_inherited_bounds_do_not_apply_to_pre_or_independent_formal(self):
        for kind, preserve in [('pre', True), ('formal', False)]:
            self.rules.update(defense_type=kind, preserve_pre_defense_groups=preserve)
            self.payload['students'][0]['previous_group_id'] = 'G1'
            self.assertEqual(inherited_group_size_issues(self.payload, self.rules), [])
