from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'minute': '天文潮预报时点',
    'depth': '潮位增水米',
    'source': '供应通告',
    'issued': '预报发布时间',
    'revision': '预报版',
    'caution': '航道限航',
}


@dataclass(frozen=True, slots=True)
class TideSample:
    minute: int
    depth: float
    source: str
    issued: int
    revision: int
    caution: bool

    def __post_init__(self):
        if type(self.minute) is not int or not 0 <= self.minute <= 30000:
            raise ValueError("天文潮预报时点越界")
        if isinstance(self.depth, bool) or not isinstance(self.depth, (float, int)):
            raise ValueError("潮位增水米须为数值")
        if not isfinite(self.depth) or not -5 <= self.depth <= 5:
            raise ValueError("潮位增水米越界")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("供应通告缺失")
        if type(self.issued) is not int or not 0 <= self.issued <= 30000:
            raise ValueError("预报发布时间越界")
        if type(self.revision) is not int or not 1 <= self.revision <= 99:
            raise ValueError("预报版越界")
        if type(self.caution) is not bool:
            raise ValueError("航道限航须为布尔值")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            minute = row["minute"]
            depth = row["depth"]
            source = row["source"]
            source = source.strip() if isinstance(source, str) else source
            issued = row["issued"]
            revision = row["revision"]
            caution = row["caution"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            minute=minute,
            depth=depth,
            source=source,
            issued=issued,
            revision=revision,
            caution=caution,
        )

    def as_record(self) -> dict:
        return asdict(self)


from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Berth:
    key: str
    length: int
    chart_depth: float
    underkeel: float
    cranes: int
    closed: tuple[tuple[int,int], ...]

    def __post_init__(self):
        if not self.key or self.length < 20 or self.chart_depth <= 1 or self.underkeel < 0 or self.cranes < 1:
            raise ValueError("泊位作业参数无效")
        ordered = sorted(self.closed)
        for start,end in ordered:
            if start >= end:
                raise ValueError("泊位维修时段反向")
        if any(p[1]>n[0] for p,n in zip(ordered,ordered[1:])):
            raise ValueError("泊位维修时段重叠")

@dataclass(frozen=True, slots=True)
class Opening:
    berth: str
    start: int
    stop: int
    tide_margin: float
    cranes: int
