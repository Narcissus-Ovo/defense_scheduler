"""Retain enough mentor attendance to staff the linked formal defense."""
from collections import defaultdict

from .policies import committee_member_target, is_software_teacher, teacher_can_role


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
        elif is_software_teacher(teacher) and teacher_can_role(teacher,'expert'):
            ordinary.extend(batch)
        else:return None
    # Spread designated chairs independently of their additional expert role.
    # Otherwise every group can contain the same chair mentors, leaving nobody
    # who can chair those groups under formal supervisor avoidance.
    chair_ids={s.supervisor_id for s in chairs}
    ordinary_ids={s.supervisor_id for s in ordinary}
    minimum=int(rules['group_min']);maximum=int(rules['group_max']);target=int(rules['group_size'])
    bins=[]
    def compatible(batch):
        from algorithm import meets_chair_requirement
        ids={s.supervisor_id for s in batch}
        chair_only={tid for tid in ids if not teacher_can_role(teacher_map[tid],'expert')}
        external={tid for tid in ids if teacher_map[tid].is_external}
        can_chair=any(teacher_can_role(teacher_map[tid],'chair') and meets_chair_requirement(teacher_map[tid],rules) for tid in ids)
        return len(chair_only)<=1 and len(external)<=2 and len(ids)<=committee_member_target(rules)+int(can_chair)
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
    if sorted(s.id for batch in bins for s in batch)!=sorted(s.id for s in students):return None
    return bins
