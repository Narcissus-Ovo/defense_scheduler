"""Probe real student/group APIs in a backup of the synthetic QA database only."""
from datetime import datetime
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import secrets
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.tmp/testing-2026-10-17'
SOURCE = ROOT / '.tmp/acceptance-20261016/api.sqlite3'
OUT.mkdir(parents=True, exist_ok=True)
before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
business_db = ROOT / 'db.sqlite3'
business_before = hashlib.sha256(business_db.read_bytes()).hexdigest() if business_db.exists() else None
with sqlite3.connect(f'file:{SOURCE.as_posix()}?mode=ro', uri=True) as original:
    with sqlite3.connect(OUT / 'student-contract.sqlite3') as target:
        original.backup(target)
sys.path.insert(0, str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='defense_scheduler.settings', DJANGO_ENV='local',
    DJANGO_DB_PATH=str(OUT / 'student-contract.sqlite3'), DJANGO_SECRET_KEY='qa-contract-only-' * 4)
import django
django.setup()
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from api.models import Student, Teacher

assert Student.objects.count() == 12
assert all(n.startswith('QA') for n in Student.objects.values_list('name', flat=True))
assert all(n.startswith('QA') for n in Teacher.objects.values_list('name', flat=True))
c = APIClient()
c.force_authenticate(User.objects.get(username='acceptance-admin'))
def unwrap(response):
    assert response.status_code == 200, (response.status_code, response.data)
    return response.data.get('data', response.data) if isinstance(response.data, dict) else response.data
def rules(kind, day):
    return dict(defense_type=kind, policy_version=2, start_date=day, end_date=day,
        expert_count=5, expert_min=5, preserve_pre_defense_groups=False)
linked = unwrap(c.post('/api/schedule/generate-linked/', {
    'pre_rules': rules('pre', '2026-10-19'), 'formal_rules': rules('formal', '2026-10-20')}, format='json'))
pre, formal = linked['pre'], linked['formal']
published_pre = unwrap(c.post('/api/schedule/publish/', {
    'version_id': pre['versionId'], 'expected_revision': pre['revision']}, format='json'))
def memberships(result):
    return {s['id']: g['groupName'] for g in result['groups'] for s in g['students']}
assert memberships(pre) == memberships(formal)
students = unwrap(c.get('/api/students/'))
if isinstance(students, dict): students = students['results']
assert len(students) == 12
source, target = formal['groups'][:2]
sid = source['students'][0]['id']
unwrap(c.post('/api/schedule/adjust/', dict(action='move_student', student_id=sid,
    from_group_id=source['id'], to_group_id=target['id'], expected_revision=formal['revision'],
    preserve_secretary=True, move_mentor=True), format='json'))
moved = unwrap(c.get('/api/schedule/current/', dict(defense_type='formal', version_id=formal['versionId'])))
old = unwrap(c.get('/api/schedule/current/', dict(defense_type='pre', version_id=pre['versionId'])))
assert memberships(moved)[sid] == target['groupName']
assert memberships(old)[sid] == source['groupName']
detail = unwrap(c.get(f'/api/students/{sid}/'))
cases = [dict(id='GROUP-linked-source', status='passed', expected='正式沿用源预组序',
              actual=dict(pre_memberships=memberships(pre), formal_memberships=memberships(formal), source_pre_published=True)),
         dict(id='GROUP-move-source-stable', status='passed', expected='正式移动改变当前组且源预组不变',
              actual=dict(student_id=sid, source_pre_group=memberships(old)[sid], current_formal_group=memberships(moved)[sid])),
         dict(id='GROUP-student-current-field', status='passed' if 'currentGroup' in detail else 'failed',
              expected='真实学生列表/详情提供前端当前分组列可读取的currentGroup',
              actual=dict(list_has_currentGroup=all('currentGroup' in s for s in students), detail=detail)),
         dict(id='GROUP-student-pre-field', status='partial', expected='学生资料可读取预答辩组序，维护语义待A确认',
              actual=dict(detail_keys=sorted(detail), source_pre_group_readable_via_selected_schedule=True,
                          dedicated_pre_group_field=False))]
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == before
assert (hashlib.sha256(business_db.read_bytes()).hexdigest() if business_db.exists() else None) == business_before
report = dict(executed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
    qa_start_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    scope='真实DRF APIClient；只操作已核实QA合成库的一致性副本，不是浏览器',
    original_fixture_database_unchanged=True, business_database_unchanged=True, cases=cases,
    counts={s:sum(x['status']==s for x in cases) for s in ['passed','failed','partial']})
(OUT/'student-group-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'real-schedule.json').write_text(json.dumps(moved,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report['counts']))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8897)
    args = parser.parse_args()
    if args.serve:
        password = secrets.token_urlsafe(24)
        user = User.objects.get(username='acceptance-admin')
        user.set_password(password)
        user.save(update_fields=['password'])
        (OUT/'browser-secret.json').write_text(json.dumps(dict(username=user.username,password=password)),encoding='utf-8')
        from waitress import serve
        from django.core.wsgi import get_wsgi_application
        serve(get_wsgi_application(), host='127.0.0.1', port=args.port, threads=4)
