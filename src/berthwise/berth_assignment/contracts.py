from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'call': '候泊航次',
    'eta': '到港分钟',
    'expected': '占泊上界分钟',
    'cold_boxes': '冷藏箱数量',
    'urgent': '高候泊风险',
    'manual': '需人工复核',
    'windows': '可用泊位窗',
    'cranes_needed': '岸桥需求数',
    'max_wait': '允许等待分钟',
}


@dataclass(frozen=True, slots=True)
class AssignmentRequest:
    call: str
    eta: int
    expected: int
    cold_boxes: int
    urgent: bool
    manual: bool
    windows: tuple
    cranes_needed: int
    max_wait: int

    def __post_init__(self):
        if not isinstance(self.call, str) or not self.call.strip():
            raise ValueError("候泊航次缺失")
        if type(self.eta) is not int or not 0 <= self.eta <= 30000:
            raise ValueError("到港分钟越界")
        if type(self.expected) is not int or not 1 <= self.expected <= 4000:
            raise ValueError("占泊上界分钟越界")
        if type(self.cold_boxes) is not int or not 0 <= self.cold_boxes <= 10000:
            raise ValueError("冷藏箱数量越界")
        if type(self.urgent) is not bool:
            raise ValueError("高候泊风险须为布尔值")
        if type(self.manual) is not bool:
            raise ValueError("需人工复核须为布尔值")
        if not isinstance(self.windows, tuple):
            raise ValueError("可用泊位窗须为序列")
        if type(self.cranes_needed) is not int or not 1 <= self.cranes_needed <= 20:
            raise ValueError("岸桥需求数越界")
        if type(self.max_wait) is not int or not 1 <= self.max_wait <= 30000:
            raise ValueError("允许等待分钟越界")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            call = row["call"]
            call = call.strip() if isinstance(call, str) else call
            eta = row["eta"]
            expected = row["expected"]
            cold_boxes = row["cold_boxes"]
            urgent = row["urgent"]
            manual = row["manual"]
            windows = row["windows"]
            windows = tuple(windows)
            cranes_needed = row["cranes_needed"]
            max_wait = row["max_wait"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            call=call,
            eta=eta,
            expected=expected,
            cold_boxes=cold_boxes,
            urgent=urgent,
            manual=manual,
            windows=windows,
            cranes_needed=cranes_needed,
            max_wait=max_wait,
        )

    def as_record(self) -> dict:
        return asdict(self)


from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class Booking:
    call: str
    berth: str | None
    moor: int | None
    sail: int | None
    wait: int | None
    state: str
    reason: str
    cranes: int
    margin: float | None
