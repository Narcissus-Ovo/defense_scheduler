"""Explain provably incompatible pre-defense headcounts before scheduling."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Group, ScheduleVersion, Student, Teacher


class PreflightMentorCapacityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user('capacity-review', is_staff=True))
        self.mentor = Teacher.objects.create(name='外院导师甲', title='教授', is_external=True,
                                             available_types=['预答辩', '正式答辩'])
        self.students = [Student.objects.create(name=f'学生{i}', student_no=f'CAP-{i}',
                         campus='创新港', mentor=self.mentor, defense_types=['预答辩', '正式答辩'])
                         for i in range(7)]
        self.rules = {'policy_version': 2, 'defense_type': 'pre',
                      'start_date': '2026-04-01', 'end_date': '2026-04-15',
                      'group_size': 6, 'group_min': 5, 'group_max': 6,
                      'expert_count': 4, 'expert_min': 4}

    def preflight(self, **changes):
        response = self.client.post('/api/schedule/preflight/',
                                    {'rules': {**self.rules, **changes}}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_seven_students_two_groups_four_reviewers_reports_required_seven(self):
        result = self.preflight()
        self.assertFalse(result['canGenerate'])
        issue = next(item for item in result['errors'] if item['type'] == 'external_mentor_capacity')
        for text in ('外院导师甲', '创新港', '7 名学生', '2 组', '4 位', '至少 7 人', '上限 6 人'):
            self.assertIn(text, issue['description'])
        self.assertIn('至少 7 人', issue['suggestion'])
        self.assertEqual(issue['teacherNames'], [self.mentor.name])
        self.assertEqual(issue['count'], 7)
        self.assertEqual(len(issue['studentNames']), 5)
        self.assertFalse(ScheduleVersion.objects.exists())
        self.assertFalse(Student.objects.exclude(bound_secretary=None).exists())

    def test_seven_student_upper_limit_does_not_report_this_capacity_conflict(self):
        result = self.preflight(group_max=7)
        self.assertTrue(result['canGenerate'], result)

    def test_capacity_is_counted_separately_for_each_campus(self):
        Student.objects.filter(pk__in=[s.pk for s in self.students[:3]]).update(campus='兴庆')
        result = self.preflight()
        self.assertTrue(result['canGenerate'], result)

    def test_raised_reviewer_minimum_changes_the_required_upper_limit(self):
        result = self.preflight(group_max=7, expert_count=5, expert_min=5)
        self.assertFalse(result['canGenerate'])
        self.assertIn('至少 8 人', result['errors'][0]['description'])

    def test_formal_does_not_apply_the_pre_defense_mentor_committee_bound(self):
        result = self.preflight(defense_type='formal', expert_count=5, expert_min=5)
        self.assertTrue(result['canGenerate'], result)

    def test_generation_and_joint_generation_stop_before_the_engine_and_any_writes(self):
        with patch('algorithm.generate_schedule', side_effect=AssertionError('Scheduling must not run')) as engine:
            generated = self.client.post('/api/schedule/generate/', {'rules': self.rules}, format='json')
            self.assertEqual(generated.status_code, 400, generated.data)
            self.assertIn('至少 7 人', generated.data['error'])
            linked = self.client.post('/api/schedule/generate-linked/', {
                'pre_rules': self.rules,
                'formal_rules': {'defense_type': 'formal', 'policy_version': 2,
                                 'start_date': '2026-05-06', 'end_date': '2026-05-22'},
            }, format='json')
            self.assertEqual(linked.status_code, 400, linked.data)
            self.assertIn('至少 7 人', linked.data['error'])
            engine.assert_not_called()
        self.assertFalse(ScheduleVersion.objects.exists())
        self.assertFalse(Student.objects.exclude(bound_secretary=None).exists())

    def test_formal_preflight_checks_inherited_sizes_but_joint_preview_uses_new_groups(self):
        source = ScheduleVersion.objects.create(defense_type='pre', is_current=True)
        group = Group.objects.create(schedule_version=source, group_id='G1', campus='创新港')
        group.students.set(self.students)
        formal_rules = {**self.rules, 'defense_type': 'formal', 'expert_count': 5, 'expert_min': 5}
        response = self.client.post('/api/schedule/preflight/', {'rules': formal_rules}, format='json')
        self.assertFalse(response.data['canGenerate'], response.data)
        self.assertIn('inherited_group_size', {i['type'] for i in response.data['errors']})
        preview = self.client.post('/api/schedule/preflight/',
                                   {'rules': formal_rules, 'linked_generation': True}, format='json')
        self.assertTrue(preview.data['canGenerate'], preview.data)
        # The read-only preview flag cannot bypass the actual generation guard.
        with patch('algorithm.generate_schedule', side_effect=AssertionError('Must not schedule')) as engine:
            response = self.client.post('/api/schedule/generate/',
                                        {'rules': formal_rules, 'linked_generation': True}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            engine.assert_not_called()
        self.assertEqual(ScheduleVersion.objects.count(), 1)
