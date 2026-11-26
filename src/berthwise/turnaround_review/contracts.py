from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'call': '航次',
    'vessel': '船舶识别',
    'berth': '安排泊位',
    'eta': '预计到港分',
    'moor': '实际进泊分',
    'sail': '预计离泊分',
    'margin': '净余水深',
    'allowed': '确认可进泊',
    'handled': '复核人',
    'generation': '计划批序',
}


@dataclass(frozen=True, slots=True)
class ReviewFact:
    call: str
    vessel: str
    berth: str
    eta: int
    moor: int
    sail: int
    margin: float
    allowed: bool
    handled: str
    generation: int

    def __post_init__(self):
        if not isinstance(self.call, str) or not self.call.strip():
            raise ValueError("航次缺失")
        if not isinstance(self.vessel, str) or not self.vessel.strip():
            raise ValueError("船舶识别缺失")
        if not isinstance(self.berth, str) or not self.berth.strip():
            raise ValueError("安排泊位缺失")
        if type(self.eta) is not int or not 0 <= self.eta <= 30000:
            raise ValueError("预计到港分越界")
        if type(self.moor) is not int or not 0 <= self.moor <= 30000:
            raise ValueError("实际进泊分越界")
        if type(self.sail) is not int or not 0 <= self.sail <= 30000:
            raise ValueError("预计离泊分越界")
        if isinstance(self.margin, bool) or not isinstance(self.margin, (float, int)):
            raise ValueError("净余水深须为数值")
        if not isfinite(self.margin) or not -5 <= self.margin <= 10:
            raise ValueError("净余水深越界")
        if type(self.allowed) is not bool:
            raise ValueError("确认可进泊须为布尔值")
        if not isinstance(self.handled, str) or not self.handled.strip():
            raise ValueError("复核人缺失")
        if type(self.generation) is not int or not 1 <= self.generation <= 10000:
            raise ValueError("计划批序越界")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            call = row["call"]
            call = call.strip() if isinstance(call, str) else call
            vessel = row["vessel"]
            vessel = vessel.strip() if isinstance(vessel, str) else vessel
            berth = row["berth"]
            berth = berth.strip() if isinstance(berth, str) else berth
            eta = row["eta"]
            moor = row["moor"]
            sail = row["sail"]
            margin = row["margin"]
            allowed = row["allowed"]
            handled = row["handled"]
            handled = handled.strip() if isinstance(handled, str) else handled
            generation = row["generation"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            call=call,
            vessel=vessel,
            berth=berth,
            eta=eta,
            moor=moor,
            sail=sail,
            margin=margin,
            allowed=allowed,
            handled=handled,
            generation=generation,
        )

    def as_record(self) -> dict:
        return asdict(self)


from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class PortAudit:
    conflicts: tuple[dict,...]
    dock_minutes: int
    wait_minutes: int
    waiting: int
    run_digest: str

    @property
    def cleared(self):
        return not self.conflicts
