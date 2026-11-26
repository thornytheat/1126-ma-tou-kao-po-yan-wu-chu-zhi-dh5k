from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'call': '航次',
    'phase': '作业区',
    'queue': '候泊船次',
    'dwell': '预测占泊分',
    'free': '当前可用泊位',
    'open_delay': '潮窗等待分',
    'yard': '堆场利用率',
    'late': '靠泊超时',
    'closed': '证据完成时间',
    'severe': '高损耗航次',
}


@dataclass(frozen=True, slots=True)
class QueueObservation:
    call: str
    phase: str
    queue: int
    dwell: float
    free: int
    open_delay: int
    yard: float
    late: bool
    closed: int
    severe: bool

    def __post_init__(self):
        if not isinstance(self.call, str) or not self.call.strip():
            raise ValueError("航次缺失")
        if not isinstance(self.phase, str) or not self.phase.strip():
            raise ValueError("作业区缺失")
        if type(self.queue) is not int or not 0 <= self.queue <= 50:
            raise ValueError("候泊船次越界")
        if isinstance(self.dwell, bool) or not isinstance(self.dwell, (float, int)):
            raise ValueError("预测占泊分须为数值")
        if not isfinite(self.dwell) or not 1 <= self.dwell <= 5000:
            raise ValueError("预测占泊分越界")
        if type(self.free) is not int or not 0 <= self.free <= 30:
            raise ValueError("当前可用泊位越界")
        if type(self.open_delay) is not int or not 0 <= self.open_delay <= 30000:
            raise ValueError("潮窗等待分越界")
        if isinstance(self.yard, bool) or not isinstance(self.yard, (float, int)):
            raise ValueError("堆场利用率须为数值")
        if not isfinite(self.yard) or not 0 <= self.yard <= 1:
            raise ValueError("堆场利用率越界")
        if type(self.late) is not bool:
            raise ValueError("靠泊超时须为布尔值")
        if type(self.closed) is not int or not 0 <= self.closed <= 30000:
            raise ValueError("证据完成时间越界")
        if type(self.severe) is not bool:
            raise ValueError("高损耗航次须为布尔值")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            call = row["call"]
            call = call.strip() if isinstance(call, str) else call
            phase = row["phase"]
            phase = phase.strip() if isinstance(phase, str) else phase
            queue = row["queue"]
            dwell = row["dwell"]
            free = row["free"]
            open_delay = row["open_delay"]
            yard = row["yard"]
            late = row["late"]
            closed = row["closed"]
            severe = row["severe"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            call=call,
            phase=phase,
            queue=queue,
            dwell=dwell,
            free=free,
            open_delay=open_delay,
            yard=yard,
            late=late,
            closed=closed,
            severe=severe,
        )

    def as_record(self) -> dict:
        return asdict(self)


from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class HazardFit:
    coefficients: tuple[float,...]
    center: tuple[float,...]
    spread: tuple[float,...]
    calibrated: tuple[tuple[float,float],...]
    rows: int

    @property
    def threshold(self):
        return .64
