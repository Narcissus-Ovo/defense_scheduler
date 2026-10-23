"""Confirmed business rule: the designated secretary list determines eligibility."""
from datetime import datetime
from django.test import SimpleTestCase
from algorithm import generate_schedule, GroupDraft, TimeRange, detect_global_conflicts, parse_teacher, parse_student, parse_room


class DesignatedSecretaryTests(SimpleTestCase):
    rules = {'defense_type': 'pre', 'policy_version': 2, 'start_date': '2031-07-14', 'end_date': '2031-07-14',
             'group_size': 1, 'group_min': 1, 'group_max': 2, 'expert_count': 5, 'expert_min': 5,
             'expert_count_includes_chair': True, 'need_chair': True, 'chair_title': '副教授',
             'secretary_title': '讲师', 'supervisor_policy': 'same_group'}

    def teachers(self, title='助理教授', **overrides):
        return [{'id': n, 'name': f'专家{n}', 'title': '教授', 'roles': ['组长','普通专家']} for n in range(1,6)] + [
            {'id':6, 'name':'名单秘书', 'title':title, 'roles':['秘书'], **overrides}]

    def test_generation_uses_designated_secretary_without_rewriting_title(self):
        for title in ('助理教授', '项目博士后', '工程师'):
            with self.subTest(title=title):
                teachers=self.teachers(title)
                result=generate_schedule(teachers,[{'id':1,'name':'学生','supervisor_id':1}],
                    [{'id':1,'name':'教室','capacity':30}],self.rules)
                self.assertEqual(result['groups'][0]['secretary_id'],6)
                self.assertFalse(result['conflicts'],result['conflicts'])
                self.assertEqual(teachers[-1]['title'],title)

    def test_saved_result_accepts_designation_and_rechecks_removed_or_inactive_role(self):
        draft=GroupDraft('G1',None,[1],TimeRange(datetime(2031,7,14,9),datetime(2031,7,14,12)),1,1,[2,3,4,5],6)
        students=[parse_student({'id':1,'name':'学生','supervisor_id':1})]
        rooms=[parse_room({'id':1,'capacity':30})]
        good=detect_global_conflicts([draft],students,[parse_teacher(t) for t in self.teachers()],rooms,self.rules)
        self.assertFalse(good,good)
        for overrides in ({'roles':['普通专家']},{'is_active':False},{'roles':[]}):
            bad=detect_global_conflicts([draft],students,[parse_teacher(t) for t in self.teachers(**overrides)],rooms,self.rules)
            self.assertTrue(bad)
