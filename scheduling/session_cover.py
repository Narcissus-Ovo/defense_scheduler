"""Choose a whole-window plan from independently feasible session committees.

The exact cover includes every student group once and at most one committee
batch per nonoverlapping session. Staff/room matching validates each column
before it enters the model. This bounds the model instead of expanding every
teacher/group/time combination into a separate binary variable.
"""
from collections import Counter
from itertools import combinations
import logging
import random

from .session_assignment import match_formal_session

_logger = logging.getLogger(__name__)


def solve_session_cover(groups, students, teachers, rooms, rules, slots, seed=0):
    # First seek a plan that preserves chairs for chair seats. Expand to all
    # confirmed expert qualifications if that smaller search cannot complete.
    for reserve_chairs in (True,False):
        result=_solve_session_cover(groups,students,teachers,rooms,rules,slots,seed,reserve_chairs)
        if result is not None:return result
    return None


def _solve_session_cover(groups, students, teachers, rooms, rules, slots, seed, reserve_chairs):
    from algorithm import iter_slot_room_candidates, teacher_is_eligible
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_array
    if not groups or not rooms or not slots or len(groups)>100:
        return None
    if any(left.overlaps(right) for i,left in enumerate(slots) for right in slots[i+1:]):
        return None
    available = [{t.id:t for t in teachers if teacher_is_eligible(t,slot,[],(),rules)} for slot in slots]
    room_options = {}
    slot_indices = {slot:si for si,slot in enumerate(slots)}
    for gi,group in enumerate(groups):
        key=(group.campus,len(group.student_ids))
        if key not in room_options:
            options={si:[] for si in range(len(slots))}
            for slot,room in iter_slot_room_candidates(group,rooms,slots,{},rules):
                if slot in slot_indices:options[slot_indices[slot]].append(room.id)
            room_options[key]=options
    # Equivalent sessions share staff AND room choices. Model one capacity
    # pool instead of duplicating every binary choice for each equivalent date;
    # these duplicate columns otherwise dominate the feasibility search.
    patterns={}
    for si,eligible in enumerate(available):
        key=(tuple(eligible),tuple(tuple(options[si]) for options in room_options.values()))
        patterns.setdefault(key,[]).append(si)
    # Enumeration is bounded. Failure is not proof of infeasibility.
    if len(groups)**2*len(patterns)>150000:
        return None
    pattern_slots=list(patterns.values())
    def match_rooms(batch,si):
        matching={}
        def augment(gi,seen):
            group=groups[gi]
            for rid in room_options[group.campus,len(group.student_ids)][si]:
                if rid in seen:continue
                seen.add(rid)
                if rid not in matching or augment(matching[rid],seen):
                    matching[rid]=gi;return True
            return False
        if not all(augment(gi,set()) for gi in batch):return None
        return {gi:rid for rid,gi in matching.items()}
    pairs=list(combinations(range(len(groups)),2))
    # An odd plan uses one triple containing a fixed anchor, then pairs. Other
    # decompositions can still be handled by the existing session planner.
    triples=[(0,*pair) for pair in combinations(range(1,len(groups)),2)] if len(groups)%2 else []
    configurations=pairs+triples
    feasible={}
    rng=random.Random(seed)
    for pi,indices in enumerate(pattern_slots):
        si=indices[0]
        feasible[pi]=[batch for batch in configurations if match_formal_session(
            [groups[gi] for gi in batch],students,teachers,rules,slots[si],available=available[si],
            reserve_chairs=reserve_chairs) is not None]
        # Validate unions as complete four-group sessions, rather than assuming
        # that two independently staffed pairs can run concurrently. This lets
        # short date windows use parallel groups without sharing personnel.
        pair_options=[batch for batch in feasible[pi] if len(batch)==2]
        proposed=set()
        for attempt in range(min(1400,len(pair_options)**2)):
            left=rng.choice(pair_options);right=rng.choice(pair_options)
            batch=tuple(sorted(set(left+right)))
            if len(batch)!=4 or batch in proposed:continue
            proposed.add(batch)
            if match_formal_session([groups[gi] for gi in batch],students,teachers,rules,
                    slots[si],available=available[si],reserve_chairs=reserve_chairs) is not None:feasible[pi].append(batch)
        _logger.debug('Session pattern %d: %d pairs, %d larger batches',pi,len(pair_options),len(feasible[pi])-len(pair_options))
    columns=[];row_indices=[];column_indices=[];values=[]
    for pi,indices in enumerate(pattern_slots):
        si=indices[0]
        for batch in feasible[pi]:
            if match_rooms(batch,si) is None:continue
            idx=len(columns);columns.append((pi,batch))
            for row in (*batch,len(groups)+pi):
                row_indices.append(row);column_indices.append(idx);values.append(1.)
    if not columns:return None
    matrix=coo_array((np.asarray(values),(np.asarray(row_indices,dtype=np.int32),
        np.asarray(column_indices,dtype=np.int32))),shape=(len(groups)+len(pattern_slots),len(columns))).tocsc()
    # Seek feasibility first. Tie-breaking is reproducible, without claiming
    # that this objective optimizes the separate workload/travel preferences.
    cost=np.asarray([pattern_slots[pi][0]*.001+rng.random()*.000001 for pi,batch in columns])
    lower=np.asarray([1.]*len(groups)+[0.]*len(pattern_slots))
    upper=np.asarray([1.]*len(groups)+[len(indices) for indices in pattern_slots])
    _logger.info('Session cover: %d groups, %d availability patterns, %d configurations, reserve chairs=%s',
                 len(groups),len(pattern_slots),len(columns),reserve_chairs)
    result=milp(cost,integrality=np.ones(len(columns)),bounds=Bounds(0,1),
        constraints=LinearConstraint(matrix,lower,upper),
        options={'time_limit':15.0,'mip_rel_gap':1.0})
    _logger.info('Session cover result: %s',result.message)
    if result.x is None or np.max(np.abs(result.x-np.rint(result.x)))>1e-5:
        return None
    selected=[columns[i] for i,value in enumerate(result.x) if value>.5]
    covered=[gi for pi,batch in selected for gi in batch]
    used=Counter(pi for pi,batch in selected)
    if sorted(covered)!=list(range(len(groups))) or any(count>len(pattern_slots[pi]) for pi,count in used.items()):
        return None
    used.clear()
    assigned=[]
    for pi,batch in selected:
        assigned.append((pattern_slots[pi][used[pi]],batch))
        used[pi]+=1
    room_map={room.id:room for room in rooms}
    completed={}
    for si,batch in assigned:
        committees=match_formal_session([groups[gi] for gi in batch],students,teachers,rules,
                                        slots[si],available=available[si],reserve_chairs=reserve_chairs)
        assignments=match_rooms(batch,si)
        if committees is None or assignments is None:return None
        for gi,committee in zip(batch,committees):
            committee.room_id=assignments[gi]
            committee.campus=room_map[committee.room_id].campus
            completed[gi]=committee
    return [completed[gi] for gi in range(len(groups))]
