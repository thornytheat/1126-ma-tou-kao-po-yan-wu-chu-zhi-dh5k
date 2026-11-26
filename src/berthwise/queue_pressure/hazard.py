from math import exp, log1p, sqrt, fsum
from .contracts import HazardFit, QueueObservation

def expit(score):
    if score >= 0:
        return 1/(1+exp(-score))
    exponent=exp(score)
    return exponent/(1+exponent)

def features(queue,dwell,free,opening,yard):
    return (queue/(free+1),dwell/60,log1p(opening),yard)

def samples(rows):
    return [(features(r.queue,r.dwell,r.free,r.open_delay,r.yard),int(r.late),2 if r.severe else 1) for r in rows]

def train_pressure(raw, split, now):
    if not 0<split<=now:
        raise ValueError("候泊留出时点早于拟合或晚于截面")
    scores=[QueueObservation.parse(row) for row in raw]
    training=samples([row for row in scores if row.closed<split])
    calibration=samples([row for row in scores if split<=row.closed<now])
    if len(training)<5:
        raise ValueError("候泊历史训练样本不足")
    ys={y for _,y,_ in training}
    cols=list(zip(*(x for x,_,_ in training),strict=True))
    m=tuple(fsum(column)/len(column) for column in cols)
    spread=tuple(max(.1,sqrt(fsum((x-c)**2 for x in column)/len(column))) for c,column in zip(m,cols,strict=True))
    coef=[0.]*5
    weight_total=sum(w for _,_,w in training)
    for _ in range(90 if len(ys)>1 else 1):
        grads=[0.]*5
        for vector,truth,w in training:
            scaled=scale(vector,m,spread)
            error=(expit(fsum(a*b for a,b in zip(coef,scaled,strict=True)))-truth)*w
            for j,value in enumerate(scaled):
                grads[j]+=error*value
        for j,g in enumerate(grads):
            coef[j]-=.21*(g/weight_total + (.08*coef[j] if j else 0))
    partial=HazardFit(tuple(coef),m,spread,(),len(training))
    buckets=[[] for _ in range(5)]
    for x,y,_ in calibration:
        buckets[min(4,int(raw_score(partial,x)*5))].append(y)
    mapping=tuple(((i+.5)/5,(sum(bucket)+2*(i+.5)/5)/(len(bucket)+2)) for i,bucket in enumerate(buckets))
    return HazardFit(tuple(coef),m,spread,mapping,len(training))

def scale(x, center, spread):
    return (1.,*((a-b)/c for a,b,c in zip(x,center,spread,strict=True)))

def raw_score(model, x):
    return expit(fsum(a*b for a,b in zip(model.coefficients,scale(x,model.center,model.spread),strict=True)))

def classify(model, queue, dwell, free, delay, yard):
    x=features(queue,dwell,free,delay,yard)
    score=raw_score(model,x)
    trust=max(abs(v) for v in scale(x,model.center,model.spread)[1:])<=4
    calibrated=model.calibrated[min(4,int(score*5))][1]
    risk=calibrated>=model.threshold
    return {"raw":round(score,5),"risk":round(calibrated,5),"urgent":risk or not trust,"in_domain":trust,
            "reason":"超出训练工况" if not trust else "候泊高压" if risk else "在服务阈值内"}
