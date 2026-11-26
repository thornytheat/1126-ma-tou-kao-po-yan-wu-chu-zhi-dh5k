from dataclasses import dataclass, asdict
from .planner import book

@dataclass(frozen=True,slots=True)
class HandoverChange:
    call: str
    old: str
    new: str
    old_berth: str | None
    new_berth: str | None
    extra_wait: int | None
    affected_cold_boxes: int
    cost_cents: int

def in_state(result):
    index={}
    for item in result:
        if item.call in index:
            raise ValueError("计划复盘出现重复航次")
        index[item.call]=item
    return index

def switch_delta(prior,new,cold_boxes,fee_cents):
    if fee_cents<0:
        raise ValueError("延迟保障不能使用负价")
    current=in_state(new)
    recorded=in_state(prior)
    change=[]
    for identity in sorted(set(current)|set(recorded)):
        before=recorded.get(identity)
        after=current.get(identity)
        key_before=(before.state,before.berth,before.wait) if before else ("未入册",None,None)
        key_after=(after.state,after.berth,after.wait) if after else ("未入册",None,None)
        if key_after==key_before:
            continue
        old_status,old_berth,old_wait=key_before
        new_status,new_berth,new_wait=key_after
        reefer=cold_boxes.get(identity,0)
        if reefer<0:
            raise ValueError("冷藏箱数不能为负")
        pause=new_wait-old_wait if new_wait is not None and old_wait is not None else None
        cost=(max(0,pause or 0)*reefer*fee_cents+59)//60
        change.append(HandoverChange(identity,old_status,new_status,old_berth,new_berth,pause,reefer,cost))
    return tuple(change)

def try_exceptions(requests, baseline, alternatives, fee_cents):
    box_counts={row.call:row.cold_boxes for row in requests}
    comparisons=[]
    for scenario in alternatives:
        if not scenario["name"] or not isinstance(scenario["reserved"],dict):
            raise ValueError("泊位反事实需要名称与预留表")
        blocked={key: careful_blocks(rows) for key,rows in scenario["reserved"].items()}
        revised=book(requests,scenario["limit"],blocked)
        delta=switch_delta(baseline,revised,box_counts,fee_cents)
        comparisons.append({"scenario":scenario["name"],"available":sum(r.berth is not None for r in revised),
                            "rerouted":sum(d.old_berth!=d.new_berth for d in delta),
                            "fee_change_cents":sum(ch.cost_cents for ch in delta),
                            "calls":[asdict(row) for row in delta]})
    return comparisons

def careful_blocks(rows):
    marks=[]
    for begin,end in sorted(map(tuple,rows)):
        if begin>=end:
            raise ValueError("泊位封锁时钟必须递增")
        if marks and marks[-1][1]>=begin:
            marks[-1]=(marks[-1][0],max(marks[-1][1],end))
        else:
            marks.append((begin,end))
    return tuple(marks)
