from collections import defaultdict
from hashlib import sha256
from json import dumps
from dataclasses import asdict

def checksum(plans, windows, config):
    plan_rows=[asdict(p) for p in sorted(plans,key=lambda row:row.call)]
    evidence={key:[asdict(s) for s in sorted(items,key=lambda item:(item.berth,item.start,item.stop))]
              for key,items in windows.items()}
    return sha256(dumps([plan_rows,evidence,config],ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def audit(plans, windows, config):
    from .contracts import PortAudit
    violations=[]
    assigned=defaultdict(list)
    for record in plans:
        if record.state!="安排靠泊":
            if any(v is not None for v in (record.berth,record.moor,record.sail)):
                violations.append({"code":"rejected_with_slot","call":record.call})
            continue
        if record.berth is None or record.moor is None or record.sail is None or record.moor>=record.sail:
            violations.append({"code":"assignment_incomplete","call":record.call})
            continue
        compatible=[row for row in windows.get(record.call,()) if row.berth==record.berth and
                    row.start<=record.moor<record.sail<=row.stop and row.cranes>=record.cranes]
        if not compatible:
            violations.append({"code":"outside_tide","call":record.call})
        if record.margin is None or record.margin<0:
            violations.append({"code":"underkeel","call":record.call})
        assigned[record.berth].append(record)
    busy=0
    wait=0
    for berth,records in sorted(assigned.items()):
        latest=None
        for item in sorted(records,key=lambda row:row.moor):
            if latest and item.moor<latest.sail:
                violations.append({"code":"berth_overlap","call":item.call,"earlier":latest.call,"berth":berth})
            if latest is None or item.sail>latest.sail:
                latest=item
            busy+=item.sail-item.moor
            wait+=item.wait or 0
    waiting=sum(record.state!="安排靠泊" for record in plans)
    return PortAudit(tuple(violations),busy,wait,waiting,checksum(plans,windows,config))

def delayed_cost(orders, reefers, hourly_guarantee):
    if hourly_guarantee<0:
        raise ValueError("保障费率不可为负")
    return [{"call":row.call,"charge_cents":((row.wait or 0)*reefers.get(row.call,0)*hourly_guarantee+59)//60}
            for row in orders if row.state=="安排靠泊"]
