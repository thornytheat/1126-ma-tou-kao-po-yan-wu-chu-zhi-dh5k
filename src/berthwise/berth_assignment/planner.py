from math import ceil
from .contracts import Booking

def order_key(row):
    return not row.urgent, -(row.cold_boxes>0), row.eta+row.max_wait, row.call

def first_vacancy(opening,reserved,eta,duration,spacing=15):
    if spacing<=0 or duration<=0:
        raise ValueError("靠泊时长及清泊间隔须为正")
    cursor=max(eta,opening.start)
    cursor=(cursor+spacing-1)//spacing*spacing
    need=ceil(duration/spacing)*spacing
    for left,right in sorted(reserved):
        if cursor+need<=left:
            break
        if cursor<right:
            cursor=(right+spacing-1)//spacing*spacing
    if cursor+need<=opening.stop:
        return cursor,cursor+need
    return None

def book(calls, coverage, reserved=None):
    if coverage < 1 or coverage > 100:
        raise ValueError("每日排靠配额须在 1 至 100")
    positions={key:list(value) for key,value in (reserved or {}).items()}
    active=list(calls)
    if len({item.call for item in active})!=len(active):
        raise ValueError("排靠航次不能重复")
    outcomes=[]
    used=0
    for call in sorted(active,key=order_key):
        if call.manual:
            outcomes.append(held(call,"人工复核","模型缺少邻近工况或超分布"))
            continue
        if used>=coverage:
            outcomes.append(held(call,"下一批排靠","已达到本窗口纳入航次数"))
            continue
        proposed=[]
        for slot in call.windows:
            if slot.cranes<call.cranes_needed:
                continue
            result=first_vacancy(slot,positions.get(slot.berth,()),call.eta,call.expected)
            if result is not None:
                proposed.append((result[0],-slot.tide_margin,slot.berth,result[1],slot.cranes))
        if not proposed:
            outcomes.append(held(call,"继续候泊","无满足作业时长及岸桥数的连续安全窗"))
            continue
        start,neg,berth,stop,cranes=min(proposed)
        wait=start-call.eta
        if wait>call.max_wait:
            outcomes.append(held(call,"协调改港","安全时段晚于承诺上限"))
            continue
        positions.setdefault(berth,[]).append((start,stop))
        outcomes.append(Booking(call.call,berth,start,stop,wait,"安排靠泊","潮位和岸桥满足占泊上界",cranes,-neg))
        used+=1
    return tuple(outcomes)

def held(call, status, why):
    return Booking(call.call,None,None,None,None,status,why,call.cranes_needed,None)
