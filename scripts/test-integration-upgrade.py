"""Verify the October data migration with a newly created synthetic old database."""
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
(ROOT / '.tmp').mkdir(exist_ok=True)
database = ROOT / '.tmp' / f'upgrade-{uuid.uuid4().hex}.sqlite3'
os.environ.update(DJANGO_SETTINGS_MODULE='defense_scheduler.settings',
                  DJANGO_DB_PATH=str(database), DJANGO_SECRET_KEY='synthetic-upgrade-check-only')
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

executor = MigrationExecutor(connection)
old_target = [('api', '0009_reference_data_v2')]
executor.migrate(old_target)
apps = executor.loader.project_state(old_target).apps
RuleConfig = apps.get_model('api', 'RuleConfig')
ScheduleVersion = apps.get_model('api', 'ScheduleVersion')
Teacher = apps.get_model('api', 'Teacher')
Student = apps.get_model('api', 'Student')
teacher = Teacher.objects.create(name='合成旧外院教师', title='教授', is_external=True, roles=['主席'])
student = Student.objects.create(name='合成旧学生', student_no='UPGRADE001', mentor_id=teacher.pk)
old_pre = {'expertCount': {'target': 4, 'min': 4, 'max': None},
           'startDate': '2031-07-14', 'softWeights': {'balanceStudentCount': 23}}
formal = {'expertCount': {'target': 5, 'min': 5}, 'startDate': '2031-07-15'}
RuleConfig.objects.create(defense_type='pre', config=old_pre)
RuleConfig.objects.create(defense_type='formal', config=formal)
version = ScheduleVersion.objects.create(defense_type='pre', version=1,
    status='published', is_current=False, rules_snapshot=old_pre)
executor = MigrationExecutor(connection)
executor.migrate([('api', '0010_pre_committee_headcount')])
new_pre = RuleConfig.objects.get(defense_type='pre').config
assert new_pre['expertCount'] == {'target': 5, 'min': 5, 'max': 5, 'includesChair': True}
assert new_pre['startDate'] == old_pre['startDate']
assert new_pre['softWeights'] == old_pre['softWeights']
assert RuleConfig.objects.get(defense_type='formal').config == formal
assert ScheduleVersion.objects.get(pk=version.pk).rules_snapshot == old_pre
executor = MigrationExecutor(connection)
executor.migrate(executor.loader.graph.leaf_nodes())
latest_apps = executor.loader.project_state(executor.loader.graph.leaf_nodes()).apps
upgraded_teacher = latest_apps.get_model('api', 'Teacher').objects.get(pk=teacher.pk)
assert upgraded_teacher.expert_only is False
assert upgraded_teacher.roles == ['主席']
assert latest_apps.get_model('api', 'Student').objects.get(pk=student.pk).mentor_id == teacher.pk
assert ScheduleVersion.objects.get(pk=version.pk).rules_snapshot == old_pre
evidence = {'passed': True, 'oldSchema': '0009', 'newSchema': '0011',
            'preExperts': 5, 'customSettingsPreserved': True,
            'formalUnchanged': True, 'publishedSnapshotUnchanged': True,
            'legacyTeacherRolesPreserved': True, 'mentorLinkPreserved': True, 'expertOnlyDefaultFalse': True}
(ROOT / '.tmp' / 'upgrade-check.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
connection.close()
print('PASS synthetic schema upgrade: 0009 -> 0010 -> 0011, pre count=5; settings, published snapshots, legacy teacher roles and mentor links preserved; expert_only defaults false.')
