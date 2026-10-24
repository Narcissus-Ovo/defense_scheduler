"""Improve target headcounts without changing group identity or hard rules."""


def balance_student_groups(batches, target, minimum, maximum, movable, compatible, can_reassign=None):
    """Every accepted transfer strictly reduces squared distance to the target.

    Callers supply mentor/role constraints and protect external attendance and
    inherited formal groups through the movement and reassignment predicates.
    """
    def valid(batch):
        return minimum <= len(batch) <= maximum and compatible(batch)

    def allowed(before, after):
        return can_reassign is None or can_reassign(before, after)

    while True:
        improved = False
        for recipient in sorted(batches, key=len):
            if len(recipient) >= maximum:
                continue
            for donor in sorted(batches, key=len, reverse=True):
                if donor is recipient or len(donor) <= minimum:
                    continue
                if donor[0].campus != recipient[0].campus:
                    continue
                before = (len(donor) - target) ** 2 + (len(recipient) - target) ** 2
                after = (len(donor) - 1 - target) ** 2 + (len(recipient) + 1 - target) ** 2
                if after >= before:
                    continue
                for student in donor:
                    if not movable(student):
                        continue
                    remaining = [s for s in donor if s.id != student.id]
                    enlarged = recipient + [student]
                    if (valid(remaining) and valid(enlarged)
                            and allowed([donor, recipient], [remaining, enlarged])):
                        donor[:] = remaining
                        recipient[:] = enlarged
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
        if improved:
            continue
        # A constrained student can first move to another existing host group;
        # one of that group's students then supplies the smaller recipient.
        # The middle group's headcount is unchanged, and the same strict cost
        # reduction and hard-rule checks apply to all three groups atomically.
        for recipient in sorted(batches, key=len):
            for donor in sorted(batches, key=len, reverse=True):
                if (donor is recipient or len(donor) <= minimum or len(recipient) >= maximum
                        or len(donor) <= len(recipient) + 1 or donor[0].campus != recipient[0].campus):
                    continue
                for student in donor:
                    if not movable(student):
                        continue
                    remaining = [s for s in donor if s.id != student.id]
                    if not valid(remaining):
                        continue
                    for middle in batches:
                        if middle is donor or middle is recipient or middle[0].campus != recipient[0].campus:
                            continue
                        for outgoing in middle:
                            if not movable(outgoing):
                                continue
                            enlarged = recipient + [outgoing]
                            replaced = [s for s in middle if s.id != outgoing.id] + [student]
                            if (valid(enlarged) and valid(replaced)
                                    and allowed([donor, middle, recipient], [remaining, replaced, enlarged])):
                                donor[:] = remaining
                                middle[:] = replaced
                                recipient[:] = enlarged
                                improved = True
                                break
                        if improved:
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
        if not improved:
            return batches
