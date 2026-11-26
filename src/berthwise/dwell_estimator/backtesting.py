from math import fsum
from dataclasses import dataclass, asdict
from .contracts import CompletedCall
from .neighbors import learn,predict_dwell

@dataclass(frozen=True,slots=True)
class RouteBacktest:
    label: str
    group: str
    support: int
    mae_minutes: float | None
    share_covered: float | None
    average_slip: float | None
    manual_count: int
    bias_minutes: float | None
    source_cutoff: int

def rolling_labels(raw, cutoff, max_cutoff):
    if not 0<cutoff<max_cutoff:
        raise ValueError("回放观察时段无效")
    coverage=[]
    for entry in raw:
        row=CompletedCall.parse(entry)
        if cutoff<=row.closed<max_cutoff:
            coverage.append(row)
    return tuple(sorted(coverage,key=lambda item:(item.closed,item.call)))

def interval_width(estimated, observed):
    return {"covered": int(observed<=estimated.high), "slip": max(0.,observed-estimated.high),
            "center": observed-estimated.expected,"manual":int(estimated.manual)}

def summaries(grouped, named, snapshot):
    output=[]
    for group, rows in sorted(grouped.items()):
        count=len(rows)
        count_covered=sum(row["covered"] for row in rows)
        if count:
            bias=fsum(row["center"] for row in rows)/count
            absolute=fsum(abs(row["center"]) for row in rows)/count
            slip=fsum(row["slip"] for row in rows)/count
        else:
            bias=absolute=slip=None
        output.append(RouteBacktest(named, group, count, absolute,
                                    count_covered/count if count else None,slip,
                                    sum(row["manual"] for row in rows),bias,snapshot))
    return output

def compare_k(raw, splits, neighbors=(3, 7, 11)):
    if not neighbors or any(k<1 for k in neighbors) or len(set(neighbors))!=len(neighbors):
        raise ValueError("回放近邻数量必须互异且大于零")
    trials=[]
    for cutoff,horizon in splits:
        holdouts=rolling_labels(raw,cutoff,horizon)
        for k in neighbors:
            model=learn(raw,cutoff,k)
            grouped={route:[] for route in sorted({row.line for row in model.references})}
            for row in holdouts:
                guess=predict_dwell(model,row.line,row.boxes,row.reefer,row.draft,row.cranes,row.yard)
                grouped.setdefault(row.line,[]).append(interval_width(guess,row.duration))
            full=[row for rows in grouped.values() for row in rows]
            grouped["整体"]=full
            trials.extend(summaries(grouped,f"k={k}",cutoff))
    return tuple(trials)

def readable(entries):
    selected=[]
    for row in entries:
        item=asdict(row)
        for key in ("mae_minutes","share_covered","average_slip","bias_minutes"):
            if item[key] is not None:
                item[key]=round(item[key],4)
        selected.append(item)
    return selected
