from dataclasses import dataclass
from math import isfinite, radians, sin
from collections import defaultdict
from .contracts import Opening

@dataclass(frozen=True,slots=True)
class WeatherHold:
    key: str
    harbor: str
    begin: int
    end: int
    issued: int
    gust_kn: float
    visibility_m: int
    wind_from: int
    level: int
    revoked: bool

    def __post_init__(self):
        if self.begin>=self.end or not self.key or not self.harbor:
            raise ValueError("气象通知缺少正确时段或航区")
        if not isfinite(self.gust_kn) or not 0<=self.gust_kn<=120:
            raise ValueError("阵风测值非法")
        if not 0<=self.visibility_m<=30000 or not 0<=self.wind_from<360 or self.level<1:
            raise ValueError("气象观测范围或修订有误")

@dataclass(frozen=True, slots=True)
class WindPolicy:
    standard_heading: int
    cross_limit: float
    min_visibility: int
    installation: str

    def __post_init__(self):
        if not 0<=self.standard_heading<360 or not 0<self.cross_limit<=120 or self.min_visibility<0:
            raise ValueError("引航风限配置有误")

def accepted_notices(raw_data, cutoff):
    revisions=defaultdict(list)
    for raw in raw_data:
        report=WeatherHold(**raw)
        if report.issued<=cutoff:
            revisions[(report.harbor,report.key)].append(report)
    notices=defaultdict(list)
    for (harbor,key),reports in sorted(revisions.items()):
        revision=max(r.level for r in reports)
        entries={r for r in reports if r.level==revision}
        if len(entries)>1:
            raise ValueError(f"同版本引航预警冲突 {harbor}/{key}")
        current=next(iter(entries))
        if not current.revoked:
            notices[harbor].append(current)
    return {key:tuple(sorted(rows,key=lambda row:(row.begin,row.end,row.key))) for key,rows in sorted(notices.items())}

def across_berth(gust,wind_heading,berth_heading):
    angle=(wind_heading-berth_heading)%180
    return abs(gust*sin(radians(angle)))

def blocked_weather(reports, policy):
    rejected=[]
    for row in reports:
        gale=across_berth(row.gust_kn,row.wind_from,policy.standard_heading)
        code=[]
        if gale>policy.cross_limit:
            code.append("横风")
        if row.visibility_m<policy.min_visibility:
            code.append("能见度")
        if code:
            rejected.append({"begin":row.begin,"end":row.end,"notice":row.key,
                             "reasons":tuple(code),"crosswind_kn":round(gale,3),"berth_group":policy.installation})
    return tuple(rejected)

def intersect_wind_slot(slot, banned, grain):
    if grain<=0:
        raise ValueError("安全泊位切分步长不能为零")
    cells=[]
    for start in range(slot.start,slot.stop,grain):
        stop=min(start+grain,slot.stop)
        if any(start<r["end"] and r["begin"]<stop for r in banned):
            continue
        if cells and cells[-1][1]==start:
            cells[-1]=(cells[-1][0],stop)
        else:
            cells.append((start,stop))
    return tuple(Opening(slot.berth,begin,end,slot.tide_margin,slot.cranes) for begin,end in cells)

def adjust_weather(open_windows, records, policy_by_berth, asof, grain=15):
    known=accepted_notices(records,asof)
    reductions={}
    for berth,settings in sorted(policy_by_berth.items()):
        spec=WindPolicy(**settings)
        reductions[berth]=blocked_weather(known.get(spec.installation,()),spec)
    after={}
    incidents=[]
    for call,windows in sorted(open_windows.items()):
        choices=[]
        for slot in windows:
            allowed=intersect_wind_slot(slot,reductions.get(slot.berth,()),grain)
            choices.extend(allowed)
            lost=(slot.stop-slot.start)-sum(item.stop-item.start for item in allowed)
            if lost:
                evidence=[row for row in reductions[slot.berth] if slot.start<row["end"] and row["begin"]<slot.stop]
                incidents.append({"call":call,"berth":slot.berth,"blocked_minutes":lost,
                                  "notices":sorted({row["notice"] for row in evidence})})
        after[call]=tuple(choices)
    return after,incidents
