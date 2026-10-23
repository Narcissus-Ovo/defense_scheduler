"""October 13 acceptance diagnostics, isolated from all business databases.

Exit 0 means evidence collection completed, NOT that requirements all passed.
Inspect case status and report counts. Any harness error returns exit 1.
"""
from collections import Counter
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = (ROOT / os.environ.get('QA_OUTPUT_DIR', '.tmp/testing-' + datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d'))).resolve()
if not OUT.is_relative_to((ROOT / '.tmp').resolve()):
    raise ValueError('QA_OUTPUT_DIR must stay inside project .tmp')
OUT.mkdir(parents=True, exist_ok=True)
os.environ.update(DJANGO_SETTINGS_MODULE='defense_scheduler.settings', DJANGO_ENV='local',
    DJANGO_DB_PATH=str(OUT / 'daily.sqlite3'), DJANGO_SECRET_KEY='isolated-daily-qa-only-' * 4)
import django
django.setup()
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APIClient
from api.models import Group, Room, RuleConfig, ScheduleVersion, ScheduleWriteLock, Student, Teacher
from api.serializers import default_rule_config
from algorithm import title_rank


def seed(dataset='normal'):
    call_command('flush', interactive=False, verbosity=0)
    ScheduleWriteLock.objects.get_or_create(pk=1)
    data = json.loads((ROOT / f'tests/fixtures/qa-20261012/{dataset}.json').read_text(encoding='utf-8'))
    people = {}
    for t in data['teachers']:
        people[t['name']] = Teacher.objects.create(name=t['name'], college=t['college'], title=t['title'],
            is_external=t['isExternal'], is_software_teacher=t['isSoftwareTeacher'],
            member_eligible=t['memberEligible'], roles=t['roles'], available_types=t['availableTypes'])
    for s in data['students']:
        Student.objects.create(name=s['name'], student_no=s['studentNo'], student_type=s['studentType'],
            mentor_name=s['mentorName'], mentor=people.get(s['mentorName']), campus=s['campus'], defense_types=s['defenseTypes'])
    for r in data['rooms']:
        Room.objects.create(name=r['name'], campus=r['campus'], capacity=r['capacity'], available_times=r['availableTimes'])
    c = APIClient()
    c.force_authenticate(User.objects.create_user('qa-daily-admin', is_staff=True))
    return c


def body(response):
    return response.data.get('data', response.data) if isinstance(response.data, dict) else response.data


def generate(c, kind='pre', **overrides):
    rules = dict(defense_type=kind, policy_version=2, start_date='2026-10-12', end_date='2026-10-16',
        preserve_pre_defense_groups=False)
    rules.update(overrides)
    return c.post('/api/schedule/generate/', {'rules': rules}, format='json')


def publish(c, result):
    return c.post('/api/schedule/publish/', {
        'version_id': result['versionId'], 'expected_revision': result['revision']}, format='json')


def current(c, kind='pre'):
    return body(c.get('/api/schedule/current/', {'defense_type': kind}))


def config_case(kind, count, accepted):
    c = seed()
    config = default_rule_config(kind)
    config['expertCount'].update(target=count, min=count)
    response = c.post('/api/rule-config/', config, format='json')
    ok = response.status_code == 200 if accepted else response.status_code == 400
    return ok, dict(http=response.status_code, stored_config_count=RuleConfig.objects.count())


def committee_case(kind, expected, **overrides):
    c = seed()
    if kind == 'pre':
        Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:6])).delete()
    response = generate(c, kind, **overrides)
    assert response.status_code == 200, response.data
    result = body(response)
    counts = [len({g['chairId'], *[t['id'] for t in g['teachers']]} - {None}) for g in result['groups']]
    published = publish(c, result)
    return bool(counts) and all(n == expected for n in counts) and published.status_code == 200, dict(
        generate_http=200, committee_counts=counts, publish_http=published.status_code,
        errors=[x for x in result['conflicts'] if x['level']=='error'])


def manual_count(kind, total, should_block):
    c = seed()
    if kind == 'pre':
        Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:6])).delete()
    response = generate(c, kind, **({'expert_count': 5, 'expert_min': 4} if kind == 'pre' else {}))
    assert response.status_code == 200, response.data
    result = body(response)
    g = Group.objects.get(pk=result['groups'][0]['id'])
    expert_ids = list(g.experts.values_list('id', flat=True))
    if total - 1 < len(expert_ids):
        expert_ids = expert_ids[:total - 1]
    else:
        spare = Teacher.objects.exclude(pk__in=[g.chair_id, g.secretary_id, *expert_ids]).filter(title='教授').first()
        expert_ids.append(spare.pk)
    adjusted = c.post('/api/schedule/adjust-group/', dict(group_id=g.pk, expected_revision=result['revision'],
        group_data={'teachers': [{'id': i} for i in expert_ids]}), format='json')
    result = current(c, kind)
    published = publish(c, result)
    types = [x['type'] for x in result['conflicts'] if x['level'] == 'error']
    count_error = any('专家人数' in t or '人员冲突' in t for t in types)
    return adjusted.status_code == 200 and (count_error and published.status_code == 400 if should_block else published.status_code == 200), dict(
        adjust_http=adjusted.status_code, error_types=types, publish_http=published.status_code, requested_total=total)


def missing_case(mode):
    c = seed()
    s = Student.objects.first()
    if mode == 'unknown':
        s.mentor = None
        s.mentor_name = 'QA缺失导师'
        s.save()
    elif mode == 'empty':
        s.mentor = None
        s.mentor_name = ''
        s.save()
    elif mode == 'inactive':
        Teacher.objects.filter(pk=s.mentor_id).update(is_active=False)
    elif mode == 'filtered':
        Teacher.objects.filter(pk=s.mentor_id).update(available_types=['正式答辩'])
    response = generate(c, expert_count=5, expert_min=5)
    published = publish(c, body(response)) if response.status_code == 200 else None
    return response.status_code == 400 and ScheduleVersion.objects.count() == 0, dict(
        generate_http=response.status_code, version_count=ScheduleVersion.objects.count(),
        publish_http=published.status_code if published else None,
        conflicts=body(response).get('conflicts', []))


def external_case(count):
    c = seed(f'external-{count}')
    Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:12])).delete()
    response = generate(c, expert_count=5, expert_min=5)
    assert response.status_code == 200, response.data
    result = body(response)
    groups = [g['groupName'] for g in result['groups'] if any(s['mentorName'] == 'QA教师01' for s in g['students'])]
    checked = c.post('/api/schedule/check-conflicts/', {'defense_type': 'pre'}, format='json')
    published = publish(c, result)
    correct = len(groups) == (1 if count < 3 else 2)
    return correct and checked.status_code == 200, dict(groups=groups,
        recheck_http=checked.status_code, recheck_conflicts=body(checked), publish_http=published.status_code)


def course_case(which, split_rooms=False):
    c = seed()
    Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:6])).delete()
    busy = {'morning': '2026-10-12 10:00-11:00', 'afternoon': '2026-10-12 15:00-16:00',
        'both': '2026-10-12 10:00-11:00,2026-10-12 15:00-16:00'}[which]
    Teacher.objects.all().update(unavailable_times=busy)
    if split_rooms:
        Room.objects.all().update(available_times='2026-10-12 08:00-12:00,2026-10-12 14:00-18:00')
    response = generate(c, end_date='2026-10-12', expert_count=5, expert_min=5)
    assert response.status_code == 200, response.data
    result = body(response)
    hours = [int(g['timeRange'].split(':')[0]) for g in result['groups'] if g['timeRange']]
    published = publish(c, result)
    ok = (bool(hours) and all(h >= 12 for h in hours) and published.status_code == 200) if which == 'morning' else (
        bool(hours) and all(h < 12 for h in hours) and published.status_code == 200) if which == 'afternoon' else published.status_code == 400
    return ok, dict(busy=busy, start_hours=hours, publish_http=published.status_code,
        room_availability='明确上午下午' if split_rooms else '周一至周五全天',
        errors=[x for x in result['conflicts'] if x['level']=='error'][:8],
        error_count=sum(x['level'] == 'error' for x in result['conflicts']))


def role_change_case(mode):
    c = seed()
    Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:6])).delete()
    result = body(generate(c, expert_count=5, expert_min=5))
    g = Group.objects.get(pk=result['groups'][0]['id'])
    if mode == 'member':
        t = g.experts.first()
        patch = {'memberEligible': False}
    elif mode == 'secretary':
        t = g.secretary
        patch = {'title': '助教'}
    else:
        t = g.experts.first()
        patch = {'avoidTeacherNames': g.chair.name, 'remark': 'QA不宜同组原因'}
    response = c.patch(f'/api/teachers/{t.pk}/', patch, format='json')
    checked = current(c)
    published = publish(c,checked)
    return response.status_code==200 and published.status_code==400, dict(update_http=response.status_code,
        error_types=[x['type'] for x in checked['conflicts'] if x['level']=='error'], publish_http=published.status_code)


def software_case(count):
    c = seed()
    Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:6])).delete()
    result = body(generate(c,'formal',avoid_supervisor=False))
    g = Group.objects.get(pk=result['groups'][0]['id'])
    ids = [g.chair_id, *g.experts.values_list('pk',flat=True)]
    Teacher.objects.all().update(is_software_teacher=False, college='其他学院')
    Teacher.objects.filter(pk__in=ids[:count]).update(is_software_teacher=True)
    checked = current(c,'formal')
    published = publish(c,checked)
    return published.status_code==(400 if count==2 else 200), dict(software_reviewers=count,
        error_types=[x['type'] for x in checked['conflicts'] if x['level']=='error'], publish_http=published.status_code)


def mid_size_case(count):
    c=seed()
    Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:count])).delete()
    result=body(generate(c,'mid'))
    published=publish(c,result)
    sizes=[len(g['students']) for g in result['groups']]
    allowed=10<=count<=13
    return published.status_code==(200 if allowed else 400), dict(input_students=count,group_sizes=sizes,publish_http=published.status_code)


def linked_external():
    c = seed('external-3')
    Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:12])).delete()
    response = c.post('/api/schedule/generate-linked/', {
        'pre_rules': dict(start_date='2026-10-12',end_date='2026-10-16',expert_count=5,expert_min=5),
        'formal_rules': dict(start_date='2026-10-19',end_date='2026-10-23')},format='json')
    assert response.status_code==200,response.data
    result=body(response)
    stages={kind: [g['groupName'] for g in result[kind]['groups'] if any(s['mentorName']=='QA教师01' for s in g['students'])] for kind in ['pre','formal']}
    return all(len(groups)==2 for groups in stages.values()), dict(generate_http=200,external_groups_by_stage=stages,
        publish_http_by_stage={kind:publish(c,result[kind]).status_code for kind in ['pre','formal']})


def title_edit(title, allowed):
    c = seed()
    Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:6])).delete()
    result = body(generate(c, expert_count=5, expert_min=5))
    group = Group.objects.get(pk=result['groups'][0]['id'])
    response = c.patch(f'/api/teachers/{group.chair_id}/', {'title': title}, format='json')
    checked = current(c)
    published = publish(c, checked)
    errors = [x['type'] for x in checked['conflicts'] if x['level'] == 'error']
    ok = response.status_code == 200 and (published.status_code == 200 if allowed else published.status_code == 400)
    return ok, dict(update_http=response.status_code, title=title, error_types=errors, publish_http=published.status_code)


def internal_chair_case():
    c = seed()
    Student.objects.exclude(pk__in=list(Student.objects.values_list('pk',flat=True)[:6])).delete()
    Teacher.objects.filter(name='QA教师01').update(is_external=True)
    response = generate(c, 'formal', avoid_supervisor=False)
    assert response.status_code == 200, response.data
    result = body(response)
    chair = Teacher.objects.get(pk=result['groups'][0]['chairId'])
    return not chair.is_external, dict(chair=chair.name, is_external=chair.is_external,
        internal_eligible_count=Teacher.objects.filter(is_external=False,title='教授').count(),
        avoidance=False, note='回避关闭，全部正高软件学院标记相同且时段可用，按外院标记优先')


def random_case():
    c = seed()
    outputs = []
    for random_seed in [101, 101, 202]:
        response = generate(c, 'formal', random_seed=random_seed)
        assert response.status_code == 200, response.data
        result = body(response)
        signature = [(g['groupName'], g['chairId'], [t['id'] for t in g['teachers']]) for g in result['groups']]
        outputs.append(signature)
    # Accepting an arbitrary field is not proof of implementing random seed support.
    sources = [ROOT / p for p in ['algorithm.py', 'api/services/rules.py', 'scheduling/preferences.py']]
    has_rng = any('random.Random(' in p.read_text(encoding='utf-8') or 'default_rng(' in p.read_text(encoding='utf-8') for p in sources)
    return has_rng and outputs[0] == outputs[1], dict(same_seed_equal=outputs[0] == outputs[1],
        different_seed_equal=outputs[0] == outputs[2], rng_implementation_found_in_current_entries=has_rng,
        note='不同种子相同输出单独不能证明失败；结合入口仍为确定性排序，仅证明当前缺实现线索，不验收随机分布')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--only',help='Optional comma-separated case IDs or prefixes; diagnostics only')
    selected=parser.parse_args().only
    root_db = ROOT / 'db.sqlite3'
    fingerprint = lambda: hashlib.sha256(root_db.read_bytes()).hexdigest() if root_db.exists() else None
    before = fingerprint()
    call_command('migrate', verbosity=0)
    cases = []
    def run(case_id, task, expected, function):
        if selected and not any(case_id.startswith(prefix) for prefix in selected.split(',')):
            return
        try:
            ok, actual = function()
            cases.append(dict(id=case_id, task=task, expected=expected, actual=actual, status='passed' if ok else 'failed'))
        except Exception as exc:
            cases.append(dict(id=case_id, task=task, expected=expected, status='error', error=f'{type(exc).__name__}: {exc}'))
        print(f'{case_id}: {cases[-1]["status"]}', flush=True)
    for kind, count, accepted in [('pre', 4, False), ('pre', 5, True), ('formal', 4, False), ('formal', 5, True), ('formal', 6, False)]:
        run(f'CFG-{kind}-{count}', 'P04', f'规则保存{kind} {count}人应{"允许" if accepted else "拒绝"}', lambda k=kind,n=count,a=accepted: config_case(k,n,a))
    for title, rank in [('教授', 3), ('研究员', 3), ('副教授', 2), ('副研究员', 2), ('讲师', 1)]:
        run(f'TITLE-{title}', 'P04', f'职称跨层口径一致，算法等级为{rank}', lambda t=title,r=rank: (title_rank(t) == r, {'algorithm_rank': title_rank(t), 'expected_rank': r}))
    run('GEN-pre-default', 'P04', '预默认5位委员会且可发布', lambda: committee_case('pre',5))
    run('GEN-pre-five', 'P04', '显式预5人配置生效并可发布', lambda: committee_case('pre',5,expert_count=5,expert_min=5))
    run('GEN-formal-five', 'P04', '正式恰好5位含主席并可发布', lambda: committee_case('formal',5))
    run('GEN-mid-five', 'P04', '中期至少5位含组长并可发布', lambda: committee_case('mid',5))
    for size in [9,10,12,13,14]:
        run(f'MID-size-{size}','P04/P05',f'中期{size}学生：10～13可行，其余此单批次人数不可发布',lambda n=size:mid_size_case(n))
    run('EDIT-pre-four', 'P04', '预手调至总4人重验标错且禁止发布', lambda: manual_count('pre',4,True))
    run('EDIT-formal-six', 'P04', '正式手调至6人重验标错且禁止发布', lambda: manual_count('formal',6,True))
    run('EDIT-title-lecturer', 'P04', '预组长变讲师后拒绝发布', lambda: title_edit('讲师',False))
    run('EDIT-title-researcher', 'P04', '正高研究员符合预组长资格', lambda: title_edit('研究员',True))
    for mode in ['unknown','empty','inactive','filtered']:
        run('MENTOR-'+mode, 'P07', '导师资料无效时生成前拒绝且无新版本', lambda m=mode: missing_case(m))
    for count in [2,3,4]:
        run(f'EXTERNAL-{count}', 'P05', f'外院{count}学生应集中{1 if count < 3 else 2}组，重验发布一致', lambda n=count: external_case(n))
    for which in ['morning','afternoon','both']:
        run('COURSE-'+which, 'P07', '有课整个半天不能排，两半天皆占用不可发布', lambda w=which: course_case(w))
    for which in ['morning','afternoon']:
        run('COURSE-split-'+which,'P07','教室显式分半天时避开有课半天，另一半天可发布',lambda w=which:course_case(w,True))
    for mode in ['member','secretary','forbidden']:
        run('ROLE-'+mode,'P04/P07','资料资格/不宜同组变化后重验并阻止错误发布',lambda m=mode:role_change_case(m))
    for count in [2,3]:
        run(f'SOFTWARE-{count}','P06','正式软件学院主体3/5边界发布一致',lambda n=count:software_case(n))
    run('LINKED-external-three','P05','联排两个阶段外院3名学生分2组或硬冲突拒绝发布',linked_external)
    run('RANDOM-seed', 'P06', '本轮随机补充且同种子可复现，不能仅保存未使用字段', random_case)
    run('CHAIR-internal-priority', 'P06', '同等正高资格及可用条件下院内主席优先', internal_chair_case)
    for case_id, task, reason in [('FULLDAY-definition','P08','整天定义未获A确认'),
        ('BALANCE-tolerance','P06','尽量均等的资源受限容差与抽取口径未确认'),
        ('QUALITY-formula','P09','评分公式与缺数据分母未获确认')]:
        if not selected:
            cases.append(dict(id=case_id, task=task, status='blocked', expected=reason, actual='不自行制定标准'))
    report = dict(date=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat(), timezone='Asia/Shanghai', recorded_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(), branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
        scope='真实Django/DRF服务，隔离SQLite与APIClient测试认证；非浏览器验收', cases=cases,
        counts=dict(Counter(c['status'] for c in cases)), business_db_sha256_before=before,
        business_db_sha256_after=fingerprint(), business_db_unchanged=before == fingerprint())
    if not cases:
        raise SystemExit('No matching cases; no verification was performed')
    (OUT / ('selected-results.json' if selected else 'daily-results.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['counts'],ensure_ascii=False))
    raise SystemExit(int(any(c['status']=='error' for c in cases)))


if __name__ == '__main__':
    main()
