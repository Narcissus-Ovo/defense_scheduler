"""Travel and reviewer workload preferences; none is a feasibility constraint."""
from collections import defaultdict
from datetime import date

from .policies import is_software_teacher, scenario_policy, teacher_can_role


_WEIGHT_NAMES = {
    'external_mentor_concentration': 'externalMentorConcentration',
    'balance_software_participation': 'balanceSoftwareParticipation',
}


def preference_weight(rules, name, default=0):
    """Use explicit engine weights, then the shared V2 scenario defaults."""
    camel_name = _WEIGHT_NAMES[name]
    weights = rules.get('soft_weights') or rules.get('softWeights') or {}
    value = weights.get(name, weights.get(camel_name))
    if value is None and (rules.get('policy_version', 1) >= 2 or rules.get('expert_count_includes_chair')):
        try:
            value = scenario_policy(rules.get('defense_type', 'pre'))['softWeights'].get(camel_name, default)
        except ValueError:
            value = default
    try:
        return max(0, min(100, int(value if value is not None else default)))
    except (TypeError, ValueError):
        return default


def external_visit_cost(draft, students, teachers, teacher_busy, rules):
    """Penalize another travel day for external teachers already attending.

    A first visit is free. The caller compares this cost only after mandatory
    role, count, availability, continuity and session constraints.
    """
    weight = preference_weight(rules, 'external_mentor_concentration')
    if weight <= 0 or draft.time_slot is None:
        return 0
    teacher_map = {teacher.id: teacher for teacher in teachers}
    people = {draft.chair_id, draft.secretary_id, *draft.expert_ids,
              *[student.supervisor_id for student in students]} - {None}
    extra_days = 0
    for tid in people:
        teacher = teacher_map.get(tid)
        if teacher is None or not teacher.is_external:
            continue
        attended_days = {slot.start.date() for slot in teacher_busy.get(tid, [])}
        if attended_days and draft.time_slot.start.date() not in attended_days:
            extra_days += 1
    return extra_days * weight


def external_full_day_gain(draft, teachers, teacher_busy, rules):
    """Count external teachers who would achieve a "full day" with this assignment.

    A full day means the teacher already has sessions in the OTHER half (morning/afternoon)
    of the same day, and adding this trial completes both halves. Higher is better.
    """
    if draft.time_slot is None or not rules.get('prefer_full_day_external', True):
        return 0
    teacher_map = {teacher.id: teacher for teacher in teachers}
    people = {draft.chair_id, draft.secretary_id, *draft.expert_ids} - {None}
    day = draft.time_slot.start.date()
    is_morning = draft.time_slot.start.hour < 12
    gain = 0
    for tid in people:
        teacher = teacher_map.get(tid)
        if teacher is None or not teacher.is_external:
            continue
        same_day_slots = [s for s in teacher_busy.get(tid, [])
                          if s.start.date() == day]
        if not same_day_slots:
            continue
        has_other_half = any((s.start.hour < 12) != is_morning for s in same_day_slots)
        if has_other_half:
            gain += 1
    return gain


def software_reviewer_load(teacher, reviewer_load, rules):
    """Rotate software-college reviewers when balancing has positive weight."""
    if preference_weight(rules, 'balance_software_participation', 50) <= 0:
        return 0
    return reviewer_load.get(teacher.id, 0)


def preference_notices(drafts, teachers, rules):
    """Explain remaining optimization opportunities without blocking publication."""
    teacher_map = {teacher.id: teacher for teacher in teachers}
    visits, reviews, review_groups = defaultdict(list), defaultdict(int), defaultdict(list)
    for group in drafts:
        if group.time_slot is None:
            continue
        for tid in {group.chair_id, group.secretary_id, *group.expert_ids} - {None}:
            visits[tid].append(group)
        for tid in {group.chair_id, *group.expert_ids} - {None}:
            reviews[tid] += 1
            review_groups[tid].append(group.group_id)
    notices = []
    if preference_weight(rules, 'external_mentor_concentration') > 0:
        for tid, groups in visits.items():
            teacher = teacher_map.get(tid)
            days = {group.time_slot.start.date() for group in groups}
            if teacher is not None and teacher.is_external and len(days) > 1:
                notices.append({
                    'type': 'external_mentor_concentration',
                    'description': f'外院教师 {teacher.name} 需在 {len(days)} 天到场，可在人员与教室允许时进一步集中安排',
                    'related_ids': [*[group.group_id for group in groups], tid],
                    'teacher_name': teacher.name,
                })

    # 外院教师半天到访提示：统计每位外院教师的整天/半天情况
    # 仅在启用外院集中安排优化时生成提示
    if rules.get('prefer_full_day_external', True) and preference_weight(rules, 'external_mentor_concentration') > 0:
        for tid, groups in visits.items():
            teacher = teacher_map.get(tid)
            if teacher is None or not teacher.is_external:
                continue
            # 按日期分组，判断每天是上午、下午还是整天
            day_halves: dict[date, set[str]] = defaultdict(set)
            for group in groups:
                if group.time_slot is None:
                    continue
                day = group.time_slot.start.date()
                half = 'morning' if group.time_slot.start.hour < 12 else 'afternoon'
                day_halves[day].add(half)
            total_days = len(day_halves)
            full_days = sum(1 for halves in day_halves.values() if len(halves) == 2)
            half_days = total_days - full_days
            # 仅在总到访天数 >= 2 且存在半天时提示
            # 只来 1 天且半天属于正常场景（可能只有 1 组需要该外院专家）
            if half_days > 0 and total_days >= 2:
                half_day_list = sorted(
                    d for d, halves in day_halves.items() if len(halves) == 1
                )
                day_descs = '、'.join(
                    f'{d.month}月{d.day}日' for d in half_day_list[:3]
                )
                if len(half_day_list) > 3:
                    day_descs += f' 等 {len(half_day_list)} 天'
                notices.append({
                    'type': 'external_half_day_visit',
                    'description': (
                        f'外院教师 {teacher.name} 在 {day_descs} 只有半天场次，'
                        f'建议调整为整天安排以减少来访次数（共到访 {total_days} 天，'
                        f'其中整天 {full_days} 天、半天 {half_days} 天）'
                    ),
                    'related_ids': [*[group.group_id for group in groups], tid],
                    'teacher_name': teacher.name,
                    'total_days': total_days,
                    'full_days': full_days,
                    'half_days': half_days,
                })

    # 同日跨校区提示：教师同一天在两个校区都有场次
    if int((rules.get('soft_weights') or {}).get('avoid_cross_campus', 0) or 0) > 0:
        for tid, groups in visits.items():
            teacher = teacher_map.get(tid)
            if teacher is None:
                continue
            day_campuses: dict[date, set[str]] = defaultdict(set)
            for group in groups:
                if group.time_slot is None or not group.campus:
                    continue
                day = group.time_slot.start.date()
                day_campuses[day].add(group.campus)
            cross_days = [d for d, campuses in day_campuses.items() if len(campuses) > 1]
            if cross_days:
                day_descs = '、'.join(
                    f'{d.month}月{d.day}日' for d in sorted(cross_days)[:3]
                )
                if len(cross_days) > 3:
                    day_descs += f' 等 {len(cross_days)} 天'
                notices.append({
                    'type': 'cross_campus_same_day',
                    'description': (
                        f'教师 {teacher.name} 在 {day_descs} 需要往返不同校区，'
                        f'建议尽量调整以减少跨校区奔波'
                    ),
                    'related_ids': [*[group.group_id for group in groups], tid],
                    'teacher_name': teacher.name,
                })

    balance_default = 50 if rules.get('policy_version', 1) >= 2 or rules.get('expert_count_includes_chair') else 0
    if rules.get('defense_type') == 'formal' and preference_weight(rules, 'balance_software_participation', balance_default) > 0:
        eligible = [teacher for teacher in teachers if is_software_teacher(teacher.raw)
                    and (teacher_can_role(teacher.raw, 'chair') or teacher_can_role(teacher.raw, 'expert'))]
        if eligible:
            minimum, maximum = min(reviews[t.id] for t in eligible), max(reviews[t.id] for t in eligible)
            if maximum - minimum > 1:
                high = [t for t in eligible if reviews[t.id] == maximum]
                low = [t for t in eligible if reviews[t.id] == minimum]
                high_names = '、'.join(t.name for t in high[:3])
                low_names = '、'.join(t.name for t in low[:3])
                diff = maximum - minimum
                notices.append({
                    'type': 'software_participation_imbalance',
                    'description': (
                        f'软件学院教师评审次数差异为 {diff} 次（最多 {maximum} 次：{high_names}；'
                        f'最少 {minimum} 次：{low_names}）。'
                        f'次数均衡为优化目标，不计入硬冲突，可在资格与时间允许时继续轮换均衡'
                    ),
                    'difference': diff,
                    'max_count': maximum,
                    'max_teacher_names': [teacher.name for teacher in high[:3]],
                    'min_count': minimum,
                    'min_teacher_names': [teacher.name for teacher in low[:3]],
                    'related_ids': [*[group_id for t in high for group_id in review_groups[t.id]],
                                    *[t.id for t in [*high[:3], *low[:3]]]],
                })
    return notices
