from collections import defaultdict
from math import isclose

def forecast_index(rows, now):
    versions = defaultdict(list)
    for event in rows:
        if event.issued <= now:
            versions[event.minute].append(event)
    out = {}
    for minute, forecasts in sorted(versions.items()):
        maximum=max((row.revision,row.issued) for row in forecasts)
        strongest={row for row in forecasts if (row.revision,row.issued)==maximum}
        readings={(row.depth,row.caution) for row in strongest}
        if len(readings) != 1:
            continue
        winner=min(strongest,key=lambda row:row.source)
        out[minute]=(winner.depth,winner.caution)
    return out

def least_depth(index, start, end, grain):
    if start % grain or end % grain or end <= start:
        raise ValueError("潮位窗口需对齐采样频率")
    readings=[index.get(mark) for mark in range(start,end+grain,grain)]
    if any(sample is None or sample[1] for sample in readings):
        return None
    return min(sample[0] for sample in readings)

def overlaps(span, other):
    return span[0] < other[1] and other[0] < span[1]

def windows(index, berth, vessel, start, horizon, grain=15):
    from .contracts import Opening
    if grain <= 0 or start >= horizon:
        raise ValueError("潮位计划时间窗无效")
    if vessel.length + 15 > berth.length:
        return ()
    floor = max(vessel.eta, start)
    ceil = ((floor+grain-1)//grain)*grain
    release = []
    for at in range(ceil, horizon-grain+1, grain):
        segment=(at,at+grain)
        if any(overlaps(segment, blocked) for blocked in berth.closed):
            continue
        tide = least_depth(index, *segment, grain)
        if tide is None:
            continue
        remaining = round(berth.chart_depth + tide - vessel.draft - berth.underkeel, 5)
        if remaining < 0 and not isclose(remaining,0,abs_tol=1e-6):
            continue
        if release and release[-1].stop == at:
            prior=release.pop()
            release.append(Opening(prior.berth,prior.start,at+grain,min(prior.tide_margin,remaining),berth.cranes))
        else:
            release.append(Opening(berth.key,at,at+grain,remaining,berth.cranes))
    return tuple(release)
