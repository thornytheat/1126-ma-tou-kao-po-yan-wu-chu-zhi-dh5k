from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'call': '结案航次',
    'line': '航线',
    'arrived': '到港分钟',
    'closed': '结案分钟',
    'boxes': '完成箱量',
    'reefer': '冷藏比例',
    'draft': '吃水米',
    'cranes': '作业桥吊',
    'yard': '堆场占用比例',
    'duration': '占泊分钟',
    'late': '靠泊超过 SLA',
}


@dataclass(frozen=True, slots=True)
class CompletedCall:
    call: str
    line: str
    arrived: int
    closed: int
    boxes: int
    reefer: float
    draft: float
    cranes: int
    yard: float
    duration: int
    late: bool

    def __post_init__(self):
        if not isinstance(self.call, str) or not self.call.strip():
            raise ValueError("结案航次缺失")
        if not isinstance(self.line, str) or not self.line.strip():
            raise ValueError("航线缺失")
        if type(self.arrived) is not int or not 0 <= self.arrived <= 30000:
            raise ValueError("到港分钟越界")
        if type(self.closed) is not int or not 0 <= self.closed <= 30000:
            raise ValueError("结案分钟越界")
        if type(self.boxes) is not int or not 1 <= self.boxes <= 10000:
            raise ValueError("完成箱量越界")
        if isinstance(self.reefer, bool) or not isinstance(self.reefer, (float, int)):
            raise ValueError("冷藏比例须为数值")
        if not isfinite(self.reefer) or not 0 <= self.reefer <= 1:
            raise ValueError("冷藏比例越界")
        if isinstance(self.draft, bool) or not isinstance(self.draft, (float, int)):
            raise ValueError("吃水米须为数值")
        if not isfinite(self.draft) or not 1 <= self.draft <= 25:
            raise ValueError("吃水米越界")
        if type(self.cranes) is not int or not 1 <= self.cranes <= 20:
            raise ValueError("作业桥吊越界")
        if isinstance(self.yard, bool) or not isinstance(self.yard, (float, int)):
            raise ValueError("堆场占用比例须为数值")
        if not isfinite(self.yard) or not 0 <= self.yard <= 1:
            raise ValueError("堆场占用比例越界")
        if type(self.duration) is not int or not 1 <= self.duration <= 2500:
            raise ValueError("占泊分钟越界")
        if type(self.late) is not bool:
            raise ValueError("靠泊超过 SLA须为布尔值")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            call = row["call"]
            call = call.strip() if isinstance(call, str) else call
            line = row["line"]
            line = line.strip() if isinstance(line, str) else line
            arrived = row["arrived"]
            closed = row["closed"]
            boxes = row["boxes"]
            reefer = row["reefer"]
            draft = row["draft"]
            cranes = row["cranes"]
            yard = row["yard"]
            duration = row["duration"]
            late = row["late"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            call=call,
            line=line,
            arrived=arrived,
            closed=closed,
            boxes=boxes,
            reefer=reefer,
            draft=draft,
            cranes=cranes,
            yard=yard,
            duration=duration,
            late=late,
        )

    def as_record(self) -> dict:
        return asdict(self)


from dataclasses import dataclass
from math import fsum

@dataclass(frozen=True, slots=True)
class NeighborModel:
    references: tuple[CompletedCall, ...]
    midpoint: tuple[float,...]
    scale: tuple[float,...]
    count: int
    maximum_distance: float

    def features(self, boxes, reefer, draft, cranes, yard):
        return (boxes / cranes, reefer, draft, yard)

    def distance(self, x, y):
        return fsum(abs(a-b)/s for a,b,s in zip(x,y,self.scale,strict=True))

@dataclass(frozen=True, slots=True)
class DwellEstimate:
    expected: float
    high: float
    support: int
    distance: float
    manual: bool
    neighbors: tuple[str,...]
