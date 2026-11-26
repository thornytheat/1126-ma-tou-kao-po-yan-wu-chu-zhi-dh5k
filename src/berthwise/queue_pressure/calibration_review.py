from collections import defaultdict
from dataclasses import dataclass, asdict
from math import fsum, log
from .contracts import QueueObservation
from .hazard import classify

@dataclass(frozen=True,slots=True)
class PortMetrics:
    phase: str
    rows: int
    coverage: float | None
    positive: int
    flagged: int
    missed: int
    false_alarm: int
    average_precision: float | None
    brier: float | None
    cross_entropy: float | None
    weighted_shift: float | None

def precision_recall_pairs(evaluations):
    tied=defaultdict(list)
    for probability,label in evaluations:
        tied[probability].append(label)
    positives=sum(label for labels in tied.values() for label in labels)
    found=0
    correct=0
    now=0.
    result=[]
    for threshold,labels in sorted(tied.items(),reverse=True):
        accepted=sum(labels)
        found+=len(labels)
        correct+=accepted
        precision=correct/found
        recall=correct/positives if positives else None
        now+=accepted*precision
        result.append({"cut":threshold,"precision":precision,"recall":recall,"selected":found})
    return (now/positives if positives else None),result

def cross_entropy(rows):
    if not rows:
        return None
    losses=[]
    for score,actual in rows:
        p=min(1.-1e-10,max(1e-10,score))
        losses.append(-log(p if actual else 1-p))
    return fsum(losses)/len(losses)

def error_table(phase, rows, threshold):
    count=len(rows)
    evaluate=[record for record in rows if record["in_domain"]]
    checked=[(row["risk"],row["actual"]) for row in evaluate]
    ap,curve=precision_recall_pairs(checked)
    losses=[(row["risk"]-row["actual"])**2 for row in evaluate]
    drift=[row["risk"]-row["raw"] for row in evaluate]
    flags=[row["risk"]>=threshold or not row["in_domain"] for row in rows]
    missed=sum(not flag and row["actual"] for flag,row in zip(flags,rows,strict=True))
    false=sum(flag and not row["actual"] for flag,row in zip(flags,rows,strict=True))
    report=PortMetrics(phase,count,len(evaluate)/count if count else None,
                       sum(row["actual"] for row in rows),sum(flags),missed,false,ap,
                       fsum(losses)/len(losses) if losses else None,cross_entropy(checked),
                       fsum(drift)/len(drift) if drift else None)
    return report,curve

def replay_outcomes(model, raw, since, until, targets=(.45,.64,.8)):
    if since>=until or len(set(targets))!=len(targets) or any(not 0<=value<=1 for value in targets):
        raise ValueError("候泊复盘窗或处置阈值有误")
    issued={}
    segments=defaultdict(list)
    for payload in raw:
        fact=QueueObservation.parse(payload)
        if not since<=fact.closed<until:
            continue
        if fact.call in issued:
            raise ValueError("候泊回放航次重复")
        verdict=classify(model,fact.queue,fact.dwell,fact.free,fact.open_delay,fact.yard)
        row=dict(verdict,actual=fact.late)
        issued[fact.call]=row
        segments[fact.phase].append(row)
    segments["所有航区"]=list(issued.values())
    evidence=[]
    for threshold in targets:
        for phase,rows in sorted(segments.items()):
            counters,curve=error_table(phase,rows,threshold)
            item=asdict(counters)
            item.update(operating_cut=threshold,curve=curve)
            evidence.append(item)
    return evidence
