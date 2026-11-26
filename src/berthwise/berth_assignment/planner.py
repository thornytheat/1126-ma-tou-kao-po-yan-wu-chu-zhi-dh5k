from math import ceil, isfinite
from collections.abc import Mapping
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


def _number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        return None
    value=float(value)
    return value if isfinite(value) and value>0 else None


def _estimate_parts(value):
    """Return (upper bound, explicit out-of-domain marker)."""
    if value is None:
        return None, True
    if isinstance(value,Mapping):
        if value.get("manual") is True or value.get("in_domain") is False:
            return None, True
        for key in ("high","upper","upper_bound","expected","duration"):
            if key in value:
                number=_number(value[key])
                if number is not None:
                    return number, False
        return None, False
    if hasattr(value,"manual") and getattr(value,"manual") is True:
        return None, True
    if hasattr(value,"in_domain") and getattr(value,"in_domain") is False:
        return None, True
    for attr in ("high","upper","upper_bound"):
        if hasattr(value,attr):
            number=_number(getattr(value,attr))
            if number is not None:
                return number, False
    number=_number(value)
    return (number,False) if number is not None else (None,False)


def _scoped_mapping_value(mapping, berth, cranes):
    for key in ((berth,cranes),berth,cranes,str(cranes),f"{berth}:{cranes}"):
        if key in mapping:
            return mapping[key], True
    if "high" in mapping or "manual" in mapping or "upper" in mapping:
        return mapping, True
    return None, False


def _mapping_value(mapping, call, berth, cranes):
    for key in ((call,berth,cranes),(call,berth),(call,cranes),
                f"{call}:{berth}:{cranes}",f"{call}:{berth}",f"{call}:{cranes}"):
        if key in mapping:
            return mapping[key], True
    if call in mapping:
        value=mapping.get(call)
        if value is None:
            return None, True
        if isinstance(value,Mapping):
            found_value,found=_scoped_mapping_value(value,berth,cranes)
            if found:
                return found_value,True
        else:
            return value,True
    return _scoped_mapping_value(mapping,berth,cranes)


def _provider_upper(provider, call, berth, cranes, index=None):
    if provider is None:
        return None, False
    if callable(provider):
        for args in ((call,berth,cranes),(call,cranes),(call,berth),(call,)):
            try:
                value=provider(*args)
            except TypeError:
                continue
            return _estimate_parts(value)
        return None, False
    if isinstance(provider,(list,tuple)) and index is not None and 0<=index<len(provider):
        return _estimate_parts(provider[index])
    if isinstance(provider,Mapping):
        value,found=_mapping_value(provider,call,berth,cranes)
        if found:
            return _estimate_parts(value)
    return None, False


def candidate_upper(row, slot, providers=(), index=None):
    berth=slot.berth
    cranes=getattr(slot,"cranes",row.cranes_needed)
    for provider in providers:
        upper,ood=_provider_upper(provider,row.call,berth,cranes,index)
        if upper is not None or ood:
            return upper,ood
    for attr in ("upper_bounds","candidate_bounds","bounds","bounds_by_cranes",
                 "prediction_bounds","estimates","predictions","highs"):
        provider=getattr(row,attr,None)
        if provider is None:
            continue
        upper,ood=_provider_upper(provider,row.call,berth,cranes,index)
        if upper is not None or ood:
            return upper,ood
    for attr in ("upper","upper_bound","high","expected","expected_duration","duration"):
        if hasattr(slot,attr):
            upper,ood=_estimate_parts(getattr(slot,attr))
            if upper is not None or ood:
                return upper,ood
    return float(row.expected),False


def _overlaps(start,stop,blocks):
    return any(start<right and left<stop for left,right in blocks)


def _candidate_key(item):
    return item["start"],-item["margin"],item["berth"],item["stop"],item["cranes"]


def _build_info(row, fixed, providers, spacing=15):
    candidates=[]
    earliest=None
    ood_candidates=0
    in_domain_candidate=False
    crane_windows=0
    seen=set()
    for slot_index,slot in enumerate(row.windows):
        if slot.cranes<row.cranes_needed:
            continue
        crane_windows+=1
        upper,ood=candidate_upper(row,slot,providers,slot_index)
        if upper is None:
            if ood:
                ood_candidates+=1
            continue
        in_domain_candidate=True
        found=first_vacancy(slot,fixed.get(slot.berth,()),row.eta,upper,spacing)
        if found is not None:
            start,stop=found
            key=(start,-slot.tide_margin,slot.berth,stop,slot.cranes)
            if earliest is None or key<earliest[0]:
                earliest=(key,upper)
        need=ceil(upper/spacing)*spacing
        first=max(row.eta,slot.start)
        first=(first+spacing-1)//spacing*spacing
        last=min(slot.stop-need,row.eta+row.max_wait)
        if first>last:
            continue
        for start in range(first,int(last)+1,spacing):
            stop=start+need
            if _overlaps(start,stop,fixed.get(slot.berth,())):
                continue
            identity=(slot.berth,start,stop)
            if identity in seen:
                continue
            seen.add(identity)
            candidates.append({
                "call":row.call,"berth":slot.berth,"start":start,"stop":stop,
                "wait":start-row.eta,"margin":slot.tide_margin,
                "cranes":slot.cranes,"upper":upper,
            })
    candidates.sort(key=_candidate_key)
    all_ood=(crane_windows>0 and not in_domain_candidate and ood_candidates>0)
    return {"row":row,"candidates":candidates,"earliest":earliest,"all_ood":all_ood}


def book(calls, coverage, reserved=None, bounds=None, **options):
    if coverage < 1 or coverage > 100:
        raise ValueError("每日排靠配额须在 1 至 100")
    active=list(calls)
    if len({item.call for item in active})!=len(active):
        raise ValueError("排靠航次不能重复")

    fixed={key:[(int(left),int(right)) for left,right in value]
           for key,value in (reserved or {}).items()}
    providers=[bounds] if bounds is not None else []
    for name in ("upper_bounds","candidate_bounds","predictions","estimated",
                 "estimates","duration_for","estimator","provider","highs"):
        provider=options.get(name)
        if provider is not None and provider not in providers:
            providers.append(provider)

    ordered=sorted(active,key=order_key)
    forced={}
    infos=[]
    for row in ordered:
        if row.manual:
            forced[row.call]=held(row,"人工复核","模型缺少邻近工况或超分布")
            continue
        info=_build_info(row,fixed,providers)
        if info["all_ood"]:
            forced[row.call]=held(row,"人工复核","模型缺少邻近工况或超分布")
            continue
        infos.append(info)

    occupied={berth:list(blocks) for berth,blocks in fixed.items()}
    best_score=None
    best_choice={}
    choice={}

    def can_place(candidate):
        return not _overlaps(candidate["start"],candidate["stop"],
                             occupied.get(candidate["berth"],()))

    def place(candidate):
        occupied.setdefault(candidate["berth"],[]).append(
            (candidate["start"],candidate["stop"]))
        choice[candidate["call"]]=candidate

    def remove(candidate):
        occupied[candidate["berth"]].pop()
        choice.pop(candidate["call"],None)

    def search(index,used,wait_total,wait_vector):
        nonlocal best_score,best_choice
        if used>coverage:
            return
        if index==len(infos):
            inclusion=tuple(1 if info["row"].call in choice else 0 for info in infos)
            # Original priority order is the lexicographic inclusion vector.
            # Equal vectors are compared by total wait, then earlier waits.
            score=(inclusion,-wait_total,tuple(-value for value in wait_vector))
            if best_score is None or score>best_score:
                best_score=score
                best_choice=dict(choice)
            return

        info=infos[index]
        valid=[] if used>=coverage else [candidate for candidate in info["candidates"]
                                         if not _overlaps(candidate["start"],candidate["stop"],
                                                           occupied.get(candidate["berth"],()))]
        if valid:
            # Lexicographic priority makes scheduling this voyage preferable to
            # every later-count improvement.  Try its placements so a choice that
            # preserves a later scarce window can win on total waiting.
            for candidate in valid:
                place(candidate)
                wait_vector.append(candidate["wait"])
                search(index+1,used+1,wait_total+candidate["wait"],wait_vector)
                wait_vector.pop()
                remove(candidate)
        else:
            wait_vector.append(0)
            search(index+1,used,wait_total,wait_vector)
            wait_vector.pop()

    search(0,0,0,[])

    outcomes=[]
    info_by_call={info["row"].call:info for info in infos}
    prior_used=0
    for row in ordered:
        if row.call in forced:
            outcomes.append(forced[row.call])
            continue
        candidate=best_choice.get(row.call)
        if candidate is not None:
            outcomes.append(Booking(
                row.call,candidate["berth"],candidate["start"],candidate["stop"],
                candidate["wait"],"安排靠泊","潮位和岸桥满足占泊上界",
                candidate["cranes"],candidate["margin"]))
            prior_used+=1
            continue
        info=info_by_call[row.call]
        if prior_used>=coverage:
            outcomes.append(held(row,"下一批排靠","已达到本窗口纳入航次数"))
            continue
        earliest=info["earliest"]
        if earliest is None:
            outcomes.append(held(row,"继续候泊","无满足作业时长及岸桥数的连续安全窗"))
            continue
        (start,_neg,_berth,_stop,_cranes),_upper=earliest
        if start-row.eta>row.max_wait:
            outcomes.append(held(row,"协调改港","安全时段晚于承诺上限"))
        else:
            outcomes.append(held(row,"继续候泊","无满足作业时长及岸桥数的连续安全窗"))
    return tuple(outcomes)


def held(call, status, why):
    return Booking(call.call,None,None,None,None,status,why,call.cranes_needed,None)
