"""Observe new acceptance gaps in an isolated Django DB; this is not a pass suite.

The JSON records requirement expectations separately from observed behavior.
Never changes the business database or exposes account tokens.
"""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = (ROOT / os.environ.get('QA_OUTPUT_DIR', '.tmp/testing-2026-10-12')).resolve()
if not OUT.is_relative_to((ROOT / '.tmp').resolve()):
    raise ValueError('QA_OUTPUT_DIR must stay inside the project .tmp directory')
OUT.mkdir(parents=True, exist_ok=True)
os.environ.update(DJANGO_SETTINGS_MODULE='defense_scheduler.settings', DJANGO_ENV='local',
    DJANGO_DB_PATH=str(OUT / 'probes.sqlite3'), DJANGO_SECRET_KEY='isolated-qa-probes-only-' * 4)

import django
django.setup()
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APIClient
from api.models import Room, ScheduleVersion, ScheduleWriteLock, Student, Teacher
from api.mentor_colors import color_index, palette


def seed(name):
    call_command('flush', interactive=False, verbosity=0)
    ScheduleWriteLock.objects.get_or_create(pk=1)
    data = json.loads((ROOT / 'tests' / 'fixtures' / 'qa-20261012' / f'{name}.json').read_text(encoding='utf-8'))
    teacher_map = {}
    for row in data['teachers']:
        teacher = Teacher.objects.create(name=row['name'], college=row['college'], title=row['title'],
            is_external=row['isExternal'], is_software_teacher=row['isSoftwareTeacher'],
            is_active=row['isActive'], member_eligible=row['memberEligible'], roles=row['roles'],
            available_types=row['availableTypes'])
        teacher_map[teacher.name] = teacher
    for row in data['students']:
        Student.objects.create(name=row['name'], student_no=row['studentNo'], student_type=row['studentType'],
            mentor=teacher_map.get(row['mentorName']), mentor_name=row['mentorName'],
            campus=row['campus'], defense_types=row['defenseTypes'], remark=row['remark'])
    for row in data['rooms']:
        Room.objects.create(campus=row['campus'], name=row['name'], capacity=row['capacity'], available_times=row['availableTimes'])
    client = APIClient()
    client.force_authenticate(User.objects.create_user('qa-probe-admin', is_staff=True))
    return client


def generate(client):
    return client.post('/api/schedule/generate/', {'rules': dict(defense_type='pre', policy_version=2,
        start_date='2026-10-12', end_date='2026-10-16')}, format='json')


def main():
    call_command('migrate', verbosity=0)
    observations = []
    call_command('flush', interactive=False, verbosity=0)
    client = APIClient()
    client.force_authenticate(User.objects.create_user('qa-import-admin', is_staff=True))
    imported = {}
    for kind, route, model in [('teachers', 'teachers', Teacher), ('students', 'students', Student), ('rooms', 'rooms', Room)]:
        with (ROOT / 'tests' / 'fixtures' / 'qa-20261012' / f'normal-{kind}.xlsx').open('rb') as handle:
            response = client.post(f'/api/{route}/import_data/', {'file': handle}, format='multipart')
        assert response.status_code == 200, response.data
        imported[kind] = model.objects.count()
    assert imported == dict(teachers=56, students=48, rooms=8), imported
    client = seed('normal')
    response = generate(client)
    result = response.data.get('data', response.data)
    assert response.status_code == 200, response.data
    counts = [len({group['chairId'], *[t['id'] for t in group['teachers']]} - {None}) for group in result['groups']]
    observations.append(dict(id='OBS-001', requirement='TASK-P04 / PRD-018',
        expected='预答辩4位普通专家另加1位组长，共5位', actual=dict(http=response.status_code, committee_counts=counts),
        meets_new_expectation=all(count == 5 for count in counts)))
    client = seed('missing-mentor')
    response = generate(client)
    result = response.data.get('data', response.data)
    publish = client.post('/api/schedule/publish/', {
        'version_id': result.get('versionId'), 'expected_revision': result.get('revision')}, format='json') if response.status_code == 200 else None
    observations.append(dict(id='OBS-002', requirement='TASK-P07 / PRD-024',
        expected='缺失导师资料时阻止生成并明确提示', actual=dict(http=response.status_code,
            versions_created=ScheduleVersion.objects.count(), publish_http=publish.status_code if publish else None,
            conflicts=result.get('conflicts', [])),
        meets_new_expectation=400 <= response.status_code < 500))
    for count in (2, 3, 4):
        client = seed(f'external-{count}')
        response = generate(client)
        assert response.status_code == 200, response.data
        result = response.data.get('data', response.data)
        attended = [g['groupName'] for g in result['groups'] if any(s['mentorName'] == 'QA教师01' for s in g['students'])]
        observations.append(dict(id=f'OBS-EXT-{count}', requirement='TASK-P05 / PRD-011',
            expected=dict(external_students=count, groups=1 if count < 3 else 2),
            actual=dict(http=response.status_code, groups=attended),
            meets_new_expectation=len(attended) == (1 if count < 3 else 2)))
    names = [f'QA教师{i:02}' for i in range(1, 18)]
    slots = {name: color_index(name) for name in names}
    observations.append(dict(id='OBS-003', requirement='TASK-P10 / PRD-040',
        expected='同份排期17位导师颜色互异', actual=dict(palette_size=len(palette()), color_slots=slots, unique_slots=len(set(slots.values()))),
        meets_new_expectation=len(set(slots.values())) == 17,
        evidence_level='后端配色函数；尚未验证网页和实际导出版式'))
    record = dict(scope='In-process real Django/DRF API with isolated synthetic database; not browser acceptance',
        database=str(OUT / 'probes.sqlite3'), excel_import_counts=imported, observations=observations)
    (OUT / 'probes.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
