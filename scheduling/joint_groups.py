"""Retain enough mentor attendance to staff the linked formal defense."""
from collections import Counter, defaultdict

from .policies import committee_member_target, is_software_teacher, teacher_can_role, pre_mentor_committee


def balance_pre_student_groups(batches, teachers, rules):
    """Prefer the target while keeping a complete mentor committee in each bin."""
    from algorithm import meets_chair_requirement
    from .balance import balance_student_groups

    teacher_map = {t.id: t for t in teachers}
    required = committee_member_target(rules) + 1
    maximum = int(rules.get('group_max') or rules['group_size'])
    mentor_limit = max(5, required) if rules.get('reserve_formal_resources') else maximum

    def compatible(batch):
        ids = {s.supervisor_id for s in batch}
        if not ids <= teacher_map.keys() or len(ids) < required or len(ids) > mentor_limit:
            return False
        mentors = [teacher_map[tid] for tid in ids]
        return (sum(not teacher_can_role(t, 'expert') for t in mentors) <= 1
                and sum(t.is_external for t in mentors) <= 2
                and any(teacher_can_role(t, 'chair') and meets_chair_requirement(t, rules) for t in mentors))

    def can_reassign(before, after):
        # Students may change seats between an external mentor's existing two
        # groups, but the mentor's group identities and attendance never change.
        for original, candidate in zip(before, after):
            if ({s.supervisor_id for s in original if teacher_map[s.supervisor_id].is_external}
                    != {s.supervisor_id for s in candidate if teacher_map[s.supervisor_id].is_external}):
                return False
        if not rules.get('reserve_formal_resources'):
            return True
        # Preserve mentor attendance resources for the linked formal stage.
        # Splitting a mentor across every group leaves no group they can review
        # under supervisor avoidance; deleting an attendance can lose a seat.
        return (Counter(tid for b in before for tid in {s.supervisor_id for s in b})
                == Counter(tid for b in after for tid in {s.supervisor_id for s in b}))

    return balance_student_groups(
        batches, int(rules['group_size']), int(rules.get('group_min') or 1), maximum,
        lambda s: s.supervisor_id in teacher_map, compatible, can_reassign,
    )


def software_capacity_is_insufficient(batches, students, teachers, minimum=3):
    """A necessary upper bound; passing it is not a feasibility certificate."""
    mentors={s.supervisor_id for s in students} - {None}
    ordinary={t.id for t in teachers if is_software_teacher(t) and teacher_can_role(t,'expert')}
    occurrences=sum(len({s.supervisor_id for s in batch} & ordinary) for batch in batches)
    # Mentor avoidance requires at least two student groups in each session.
    return occurrences+len(ordinary-mentors)*(len(batches)//2)<(minimum-1)*len(batches)


def reviewer_capacity_is_insufficient(batches, students, teachers, reviewers_per_group=5):
    """Include all review seats, even when the software-majority bound passes."""
    mentors={s.supervisor_id for s in students} - {None}
    reviewers={t.id for t in teachers if teacher_can_role(t,'expert') or teacher_can_role(t,'chair')}
    occurrences=sum(len({s.supervisor_id for s in batch}&reviewers) for batch in batches)
    return occurrences+len(reviewers-mentors)*(len(batches)//2)<reviewers_per_group*len(batches)


def _transfer_via_exchange(batch, bins, internal_ids, chair_ids, required, minimum, maximum, compatible):
    """Replenish a donor through an exchange before it supplies the recipient."""
    if len(batch) >= maximum:
        return False
    mentors = {s.supervisor_id for s in batch}

    def complete(candidate):
        return (minimum <= len(candidate) <= maximum
                and len({s.supervisor_id for s in candidate}) >= required
                and any(s.supervisor_id in chair_ids for s in candidate)
                and compatible(candidate))

    for donor in bins:
        if donor is batch or len(donor) <= minimum or donor[0].campus != batch[0].campus:
            continue
        for student in donor:
            if student.supervisor_id not in internal_ids or student.supervisor_id in mentors:
                continue
            recipient = batch + [student]
            if not compatible(recipient):
                continue
            remaining = [s for s in donor if s.id != student.id]
            for source in bins:
                if source is batch or source is donor or source[0].campus != batch[0].campus:
                    continue
                for incoming in source:
                    if incoming.supervisor_id not in internal_ids:
                        continue
                    for outgoing in remaining:
                        if outgoing.supervisor_id not in internal_ids:
                            continue
                        replenished = [s for s in remaining if s.id != outgoing.id] + [incoming]
                        replacement = [s for s in source if s.id != incoming.id] + [outgoing]
                        if not complete(replenished) or not complete(replacement):
                            continue
                        batch[:] = recipient
                        donor[:] = replenished
                        source[:] = replacement
                        return True
    return False


def _redistribute_internal_mentors(bins, internal_ids, chair_ids, required, minimum, maximum, compatible):
    """Move or exchange internal students, retaining external parts and chairs."""
    for batch in bins:
        while len({s.supervisor_id for s in batch}) < required:
            mentors = {s.supervisor_id for s in batch}
            moved = False
            for donor in sorted(bins, key=lambda b: (len({s.supervisor_id for s in b}), len(b)), reverse=True):
                if donor is batch or donor[0].campus != batch[0].campus:
                    continue
                for student in donor:
                    if student.supervisor_id not in internal_ids or student.supervisor_id in mentors:
                        continue
                    remaining = [s for s in donor if s.id != student.id]
                    if (len(batch) < maximum and len(donor) > minimum
                            and len({s.supervisor_id for s in remaining}) >= required
                            and any(s.supervisor_id in chair_ids for s in remaining)
                            and compatible(batch + [student]) and compatible(remaining)):
                        donor.remove(student)
                        batch.append(student)
                        moved = True
                        break
                    # A full recipient or a minimum-size donor needs an exchange.
                    # Only move a duplicate internal mentor's student out: this
                    # strictly increases the recipient's mentor count, and leaves
                    # every external mentor's student parts in their original bins.
                    for outgoing in batch:
                        if (outgoing.supervisor_id not in internal_ids
                                or sum(s.supervisor_id == outgoing.supervisor_id for s in batch) < 2):
                            continue
                        recipient = [s for s in batch if s.id != outgoing.id] + [student]
                        replacement = remaining + [outgoing]
                        if (len({s.supervisor_id for s in replacement}) < required
                                or not any(s.supervisor_id in chair_ids for s in replacement)
                                or not compatible(recipient) or not compatible(replacement)):
                            continue
                        batch[:] = recipient
                        donor[:] = replacement
                        moved = True
                        break
                    if moved:
                        break
                if moved:
                    break
            if not moved:
                if not _transfer_via_exchange(batch, bins, internal_ids, chair_ids,
                                              required, minimum, maximum, compatible):
                    return False
    return True


def build_linked_student_groups(students, teachers, rules):
    """A role-aware alternative to single-mentor clustering, without exclusions.

    External mentor parts remain fixed by campus. Spread internal mentors over
    those parts so that their attendance can support formal review seats later.
    Only valid-size complete candidates are returned; scheduling still requires
    an independent all-constraints check in both stages.
    """
    teacher_map={t.id:t for t in teachers}
    clusters=defaultdict(list)
    for student in students:
        if student.supervisor_id not in teacher_map:return None
        clusters[student.campus,student.supervisor_id].append(student)
    ordinary=[];external_parts=[];chairs=[]
    for (campus,tid),batch in clusters.items():
        teacher=teacher_map[tid]
        if teacher.is_external:
            middle=(len(batch)+1)//2
            external_parts.extend((batch[:middle],batch[middle:]) if len(batch)>=3 else (batch,))
        elif teacher_can_role(teacher,'chair'):
            chairs.extend(batch)
        elif teacher_can_role(teacher,'expert'):
            ordinary.extend(batch)
        else:return None
    # Spread designated chairs independently of their additional expert role.
    # Otherwise every group can contain the same chair mentors, leaving nobody
    # who can chair those groups under formal supervisor avoidance.
    chair_ids={s.supervisor_id for s in chairs}
    ordinary_ids={s.supervisor_id for s in ordinary}
    target=int(rules['group_size'])
    minimum=int(rules.get('group_min', 0) or 0)
    maximum=int(rules.get('group_max', 0) or target)
    bins=[]
    def compatible(batch):
        from algorithm import meets_chair_requirement
        ids={s.supervisor_id for s in batch}
        chair_only={tid for tid in ids if not teacher_can_role(teacher_map[tid],'expert')}
        external={tid for tid in ids if teacher_map[tid].is_external}
        can_chair=any(teacher_can_role(teacher_map[tid],'chair') and meets_chair_requirement(teacher_map[tid],rules) for tid in ids)
        mentor_limit = (max(5, committee_member_target(rules)+1) if rules.get('reserve_formal_resources') else maximum) if pre_mentor_committee(rules) else committee_member_target(rules)+int(can_chair)
        return len(chair_only)<=1 and len(external)<=2 and len(ids)<=mentor_limit
    for part in sorted(external_parts,key=lambda batch:(-len(batch),batch[0].campus or '',batch[0].id)):
        external_ids={s.supervisor_id for s in part}
        host=next((batch for batch in bins if batch[0].campus==part[0].campus
            and len(batch)+len(part)<=max(1,target-2)
            and not external_ids.intersection(s.supervisor_id for s in batch) and compatible(batch+part)),None)
        if host is None:bins.append(list(part))
        else:host.extend(part)
    for student in sorted(chairs,key=lambda s:(s.campus or '',s.id)):
        eligible=[batch for batch in bins if batch[0].campus==student.campus and len(batch)<min(target,maximum)
            and compatible(batch+[student]) and sum(s.supervisor_id==student.supervisor_id for s in batch)<2
            and not ({s.supervisor_id for s in batch}&chair_ids)-{student.supervisor_id}]
        if eligible:
            host=min(eligible,key=lambda batch:(sum(s.supervisor_id in chair_ids for s in batch),len(batch)))
            host.append(student)
        else:bins.append([student])
    for student in sorted(ordinary,key=lambda s:(s.campus or '',s.id)):
        eligible=[batch for batch in bins if batch[0].campus==student.campus and len(batch)<maximum
            and compatible(batch+[student]) and not any(s.supervisor_id==student.supervisor_id for s in batch)]
        if eligible:
            host=min(eligible,key=lambda batch:(sum(s.supervisor_id in ordinary_ids for s in batch),len(batch)))
            host.append(student)
        else:bins.append([student])
    for batch in bins:
        while len(batch)<minimum:
            found=False
            for donor in sorted(bins,key=len,reverse=True):
                if len(donor)<=minimum or donor[0].campus!=batch[0].campus:continue
                movable=next((s for s in donor if s.supervisor_id in ordinary_ids and compatible(batch+[s])),None)
                if movable is not None:
                    donor.remove(movable);batch.append(movable);found=True;break
            if not found:break
    if any(not minimum<=len(batch)<=maximum or not compatible(batch) for batch in bins):return None
    if pre_mentor_committee(rules):
        from algorithm import meets_chair_requirement
        qualified_chairs = {tid for tid in chair_ids if meets_chair_requirement(teacher_map[tid], rules)}
        if not _redistribute_internal_mentors(bins, ordinary_ids | chair_ids, qualified_chairs,
                                             committee_member_target(rules)+1, minimum, maximum, compatible):
            return None
        for batch in bins:
            ids={s.supervisor_id for s in batch}
            if len(ids)<committee_member_target(rules)+1:return None
            if not any(teacher_can_role(teacher_map[tid],'chair') and meets_chair_requirement(teacher_map[tid],rules) for tid in ids):return None
    if sorted(s.id for batch in bins for s in batch)!=sorted(s.id for s in students):return None
    return bins
