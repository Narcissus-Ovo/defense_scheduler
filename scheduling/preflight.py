"""Necessary capacity bounds, without running or changing a schedule."""
from collections import defaultdict

from .policies import pre_mentor_committee, secretary_is_qualified, teacher_can_role


def external_mentor_capacity_issues(payload, rules):
    """Each reviewer needs a student; one mentor cannot occupy all student seats."""
    if not pre_mentor_committee(rules):
        return []
    maximum = int(rules.get('group_max') or rules.get('group_size') or 0)
    if not maximum:
        return []
    reviewers = max(4, int(rules.get('expert_min', 4)))
    teachers = {t['id']: t for t in payload['teachers']}
    cohorts = defaultdict(list)
    for student in payload['students']:
        mentor = teachers.get(student.get('supervisor_id'))
        if mentor and mentor.get('is_external'):
            cohorts[mentor['id'], student.get('campus')].append(student)

    issues = []
    for (mentor_id, campus), students in cohorts.items():
        count = len(students)
        groups = 1 if count < 3 else 2
        largest_part = (count + groups - 1) // groups
        required_maximum = largest_part + reviewers - 1
        if maximum >= required_maximum:
            continue
        mentor_name = teachers[mentor_id]['name']
        issues.append({
            'type': 'external_mentor_capacity',
            'level': 'error',
            'description': (
                f'外院导师 {mentor_name} 在{campus or "未填校区"}有 {count} 名学生，'
                f'按规则须安排在 {groups} 组，至少一组有其 {largest_part} 名学生；'
                f'本次至少需要 {reviewers} 位不同导师评审，且每位评审须有本组学生，'
                f'该组至少 {required_maximum} 人，与当前学生上限 {maximum} 人冲突。'
            ),
            'studentNames': [s['name'] for s in students[:5]],
            'teacherNames': [mentor_name],
            'count': count,
            'suggestion': f'请将每组学生上限调整为至少 {required_maximum} 人；外院导师分组和评审下限规则保持不变。',
        })
    return issues


def inherited_group_size_issues(payload, rules):
    if rules.get('defense_type') != 'formal' or not rules.get('preserve_pre_defense_groups', True):
        return []
    groups = defaultdict(list)
    for student in payload['students']:
        if student.get('previous_group_id') is not None:
            groups[student['previous_group_id']].append(student)
    minimum = int(rules.get('group_min') or 1)
    maximum = int(rules.get('group_max') or rules['group_size'])
    return [{
        'type': 'inherited_group_size', 'level': 'error',
        'description': f'正式答辩沿用预答辩 {label} 组，现有 {len(students)} 人，超出本次每组 {minimum}–{maximum} 人范围；沿用分组不会自动拆分或合并。',
        'suggestion': '请先调整预答辩分组或正式答辩人数范围；如需重排两阶段，请使用联合生成。',
        'studentNames': [s['name'] for s in students[:5]], 'teacherNames': [], 'count': len(students),
    } for label, students in groups.items() if not minimum <= len(students) <= maximum]


def resource_availability_issues(payload, rules):
    """Report necessary resource bounds as warnings, preserving personnel drafts.

    Passing this lightweight check is not a full matching/feasibility proof.
    """
    if rules.get('policy_version', 1) < 2 or not payload['students'] or not payload['teachers']:
        return []
    from algorithm import (GroupDraft, build_candidate_slots, is_resource_available, iter_slot_room_candidates,
                           meets_chair_requirement, parse_room, parse_teacher, parse_time_range, teacher_is_eligible)

    teachers = [parse_teacher(t) for t in payload['teachers']]
    teachers = [t for t in teachers if teacher_is_eligible(t, None, [], (), rules)]
    unavailable = {t.id: [parse_time_range(value) for value in t.available_time] for t in teachers}
    chairs = [t for t in teachers if teacher_can_role(t, 'chair') and meets_chair_requirement(t, rules)]
    secretaries = [t for t in teachers if secretary_is_qualified(t, rules.get('secretary_title', ''))]
    reviewers = {t.id for t in teachers if teacher_can_role(t, 'expert') or t in chairs}
    minimum_reviewers = int(rules.get('expert_min', 4))
    rooms = [parse_room(r) for r in payload['rooms']]
    slots = build_candidate_slots(rules, rooms)
    warnings = []

    def warn(kind, description, suggestion, names=()):
        warnings.append({'type': kind, 'level': 'warning', 'description': description,
                         'suggestion': suggestion, 'studentNames': [],
                         'teacherNames': list(names)[:5], 'count': len(names)})

    if not chairs:
        warn('chair_availability', f'没有可担任主席/组长且达到“{rules.get("chair_title", "")}”要求的教师。',
             '请核对教师角色、职称、在用状态和可参加答辩类型；也可先生成草稿核对人员。')
    if not secretaries:
        warn('secretary_availability', '没有符合本次资格要求的秘书。',
             '请核对指定秘书名单或备用职称资格、在用状态和可参加答辩类型。')
    if len(reviewers) < minimum_reviewers:
        warn('reviewer_availability', f'可担任评审的教师共 {len(reviewers)} 位，少于每组至少 {minimum_reviewers} 位。',
             '请核对教师评审资格及参加答辩类型。')

    by_campus = defaultdict(list)
    for student in payload['students']:
        by_campus[student.get('campus')].append(student)
    availability = {}
    # Room capacity is checked against the minimum acceptable reviewer count.
    room_rules = {**rules, 'expert_count': minimum_reviewers}
    for campus, students in by_campus.items():
        label = campus or '未填校区'
        smallest = min(len(students), int(rules.get('group_min') or 1))
        shell = GroupDraft('预检', campus, [s['id'] for s in students[:smallest]])
        candidates = list(iter_slot_room_candidates(shell, rooms, slots, {}, room_rules))
        if not candidates:
            warn('room_availability', f'{label}的分组未找到日期、容量与可用时间均符合要求的教室。',
                 '请核对教室时间、容量、日期及校区开始日；可先生成草稿安排人员，教室与时间稍后补齐。')
            continue
        if not chairs or not secretaries or len(reviewers) < minimum_reviewers:
            continue
        mentor_ids = {s.get('supervisor_id') for s in students} - {None}
        campus_chairs = [t for t in chairs if not pre_mentor_committee(rules) or t.id in mentor_ids]
        if not campus_chairs:
            warn('chair_availability', f'{label}学生的导师中没有符合本次资格要求的组长。',
                 '预答辩组长必须有本组学生，请核对导师的组长资格和学生校区。')
            continue
        common = set()
        required_mentors = mentor_ids if pre_mentor_committee(rules) else {None}
        for slot in dict.fromkeys(slot for slot, _room in candidates):
            key = (slot.start, slot.end)
            if key not in availability:
                availability[key] = {t.id for t in teachers if is_resource_available(unavailable[t.id], slot)}
            eligible = availability[key]
            for secretary in secretaries:
                if secretary.id not in eligible or len((reviewers & eligible) - {secretary.id}) < minimum_reviewers:
                    continue
                if any(t.id in eligible and t.id != secretary.id for t in campus_chairs):
                    common.update(tid for tid in required_mentors
                                  if tid is None or (tid in eligible and tid in reviewers and tid != secretary.id))
            if required_mentors <= common:
                break
        missing = required_mentors - common
        if missing:
            names = [t.name for t in teachers if t.id in missing]
            warn('common_availability',
                 f'{label}未找到导师、合格组长、秘书、足额评审与教室共同可用的时段'
                 + (f'，涉及 {len(missing)} 位导师：{"、".join(names[:5])}。' if names else '。'),
                 '请核对教师有课或不可用时间、角色分离、教室时段和排期日期；此预检未执行完整排期。', names)
    return warnings
