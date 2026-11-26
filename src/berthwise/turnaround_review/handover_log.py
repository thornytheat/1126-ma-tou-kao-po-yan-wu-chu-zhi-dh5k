from dataclasses import dataclass
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

@dataclass(frozen=True, slots=True)
class MooringNote:
    call: str
    berth: str
    sequence: int
    moored: int
    started: int
    ended: int
    departed: int
    cranes: int
    signed: bool
    lifted: int
    seal: str

    def __post_init__(self):
        if not self.call or not self.berth or not self.seal:
            raise ValueError("装卸签报缺少靠泊身份")
        if not self.moored<=self.started<self.ended<=self.departed:
            raise ValueError("靠泊、作业及离港时钟不同步")
        if self.sequence<1 or self.cranes<1 or self.lifted<0 or type(self.signed) is not bool:
            raise ValueError("签报中的版次、岸桥或箱量有误")

def index_confirmed(raw, closed_asof=None):
    in_records=defaultdict(list)
    for record in raw:
        row=MooringNote(**record)
        if closed_asof is None or row.departed<=closed_asof:
            in_records[row.call].append(row)
    registry={}
    faults=[]
    for call,parts in sorted(in_records.items()):
        edition=max(note.sequence for note in parts)
        versions={r for r in parts if r.sequence==edition}
        if len(versions)>1:
            faults.append({"call":call,"switch":"签报同效冲突"})
            continue
        registry[call]=next(iter(versions))
    return registry,faults

def audit_actual(plans, receipts, asof):
    notes, faults=index_confirmed(receipts, asof)
    pending={row["call"] for row in receipts if row["departed"]>asof}
    result=[]
    used=0
    planned_minutes=0
    for order in sorted(plans,key=lambda row:row.call):
        received=notes.pop(order.call,None)
        if order.berth is None:
            if received and received.departed<=asof:
                result.append({"call":order.call,"switch":"存在现场签报但无本计划"})
            continue
        if received is None:
            state="回执尚未结案" if order.call in pending else "计划待回执"
            result.append({"call":order.call,"switch":state})
            continue
        duration=received.ended-received.started
        throughput=Decimal(received.lifted*60)/Decimal(duration*received.cranes)
        difference=received.moored-order.moor
        planned_minutes+=order.sail-order.moor
        used+=received.departed-received.moored
        reason="在原泊位执行"
        if not received.signed:
            reason="签报未签"
        elif received.berth!=order.berth:
            reason="现场换泊"
        elif difference>15:
            reason="进泊延误"
        result.append({"call":order.call,"switch":reason,"booked":order.berth,"landed":received.berth,
                       "inbound_delta":difference,"efficiency":float(throughput.quantize(Decimal(".01"),rounding=ROUND_HALF_UP)),
                       "seal":received.seal,"tally":received.lifted})
    result.extend({"call":note.call,"switch":"无报港但有现场签报"} for note in notes.values() if note.departed<=asof)
    result.extend(faults)
    result.append({"occupied_real_minutes":used,"occupied_plan_minutes_for_receipts":planned_minutes})
    return result
