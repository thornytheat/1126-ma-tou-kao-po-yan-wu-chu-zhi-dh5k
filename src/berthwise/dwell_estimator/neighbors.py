from math import fsum, ceil
from statistics import median
from .contracts import CompletedCall, NeighborModel, DwellEstimate

def vector(row):
    return row.boxes/row.cranes,row.reefer,row.draft,row.yard

def learn(rows, cutoff, count=7, distance_limit=8.) -> NeighborModel:
    if count < 1 or distance_limit <= 0:
        raise ValueError("邻近参考参数须为正")
    prior=[]
    for raw in rows:
        row = CompletedCall.parse(raw)
        if row.closed <= row.arrived:
            raise ValueError("结案不能早于实际到港")
        if row.closed < cutoff:
            prior.append(row)
    if not prior:
        raise ValueError("训练窗无结案航次")
    if len({row.call for row in prior}) != len(prior):
        raise ValueError("训练窗存在重复结案")
    columns = tuple(zip(*(vector(row) for row in prior),strict=True))
    mid = tuple(median(col) for col in columns)
    spans = tuple(max(floor,median(abs(x-center) for x in col)*1.4826)
                  for col,center,floor in zip(columns,mid,(15,.03,.35,.05),strict=True))
    return NeighborModel(tuple(sorted(prior,key=lambda row:row.call)),mid,spans,count,distance_limit)

def weighted_quantile(points, p):
    if not 0 < p <= 1 or not points or any(w <= 0 for _,w in points):
        raise ValueError("样本权重或分位数无效")
    records=sorted(points)
    threshold=fsum(w for _,w in records)*p
    visit=0.0
    for value,weight in records:
        visit+=weight
        if visit>=threshold:
            return value
    return records[-1][0]

def predict_dwell(model, line, boxes, reefer, draft, cranes, yard):
    target=model.features(boxes,reefersafe(reefer),draft,cranes,yard)
    rank=[]
    for sample in model.references:
        delta=model.distance(target,vector(sample))
        delta += 0 if sample.line == line else .8
        rank.append((delta,sample.call,sample))
    neighbors=sorted(rank,key=lambda p:(p[0],p[1]))[:model.count]
    evidence=[(row.duration,1/(1+distance)) for distance,_,row in neighbors]
    center=weighted_quantile(evidence,.5)
    high=weighted_quantile(evidence,.85)
    distance=neighbors[-1][0]
    manual=distance>model.maximum_distance or len(neighbors)<min(model.count,5)
    return DwellEstimate(center,high,len(neighbors),round(distance,4),manual,
                         tuple(identity for _,identity,_ in neighbors))

def reefersafe(share):
    if not 0<=share<=1:
        raise ValueError("冷藏箱比例须在零至一")
    return share
