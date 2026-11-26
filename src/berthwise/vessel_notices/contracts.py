from dataclasses import asdict, dataclass
from math import isfinite
from typing import Self


COLUMN_LABELS = {
    'call': '航次',
    'imo': '船籍',
    'line': '航线',
    'revision': '报港版次',
    'sent': '报港分钟',
    'eta': '预计到港分钟',
    'draft': '最大吃水米',
    'boxes': '计划装卸箱',
    'perishable': '冷藏箱数',
    'length': '船长米',
    'origin': '申报来源',
    'cancelled': '撤销标记',
}


@dataclass(frozen=True, slots=True)
class Notice:
    call: str
    imo: str
    line: str
    revision: int
    sent: int
    eta: int
    draft: float
    boxes: int
    perishable: int
    length: int
    origin: str
    cancelled: bool

    def __post_init__(self):
        if not isinstance(self.call, str) or not self.call.strip():
            raise ValueError("航次缺失")
        if not isinstance(self.imo, str) or not self.imo.strip():
            raise ValueError("船籍缺失")
        if not isinstance(self.line, str) or not self.line.strip():
            raise ValueError("航线缺失")
        if type(self.revision) is not int or not 1 <= self.revision <= 200:
            raise ValueError("报港版次越界")
        if type(self.sent) is not int or not 0 <= self.sent <= 30000:
            raise ValueError("报港分钟越界")
        if type(self.eta) is not int or not 0 <= self.eta <= 30000:
            raise ValueError("预计到港分钟越界")
        if isinstance(self.draft, bool) or not isinstance(self.draft, (float, int)):
            raise ValueError("最大吃水米须为数值")
        if not isfinite(self.draft) or not 2 <= self.draft <= 20:
            raise ValueError("最大吃水米越界")
        if type(self.boxes) is not int or not 1 <= self.boxes <= 10000:
            raise ValueError("计划装卸箱越界")
        if type(self.perishable) is not int or not 0 <= self.perishable <= 10000:
            raise ValueError("冷藏箱数越界")
        if type(self.length) is not int or not 20 <= self.length <= 500:
            raise ValueError("船长米越界")
        if not isinstance(self.origin, str) or not self.origin.strip():
            raise ValueError("申报来源缺失")
        if type(self.cancelled) is not bool:
            raise ValueError("撤销标记须为布尔值")

    @classmethod
    def parse(cls, row: dict) -> Self:
        try:
            call = row["call"]
            call = call.strip() if isinstance(call, str) else call
            imo = row["imo"]
            imo = imo.strip() if isinstance(imo, str) else imo
            line = row["line"]
            line = line.strip() if isinstance(line, str) else line
            revision = row["revision"]
            sent = row["sent"]
            eta = row["eta"]
            draft = row["draft"]
            boxes = row["boxes"]
            perishable = row["perishable"]
            length = row["length"]
            origin = row["origin"]
            origin = origin.strip() if isinstance(origin, str) else origin
            cancelled = row["cancelled"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"缺少可用的业务字段 {error}") from error
        return cls(
            call=call,
            imo=imo,
            line=line,
            revision=revision,
            sent=sent,
            eta=eta,
            draft=draft,
            boxes=boxes,
            perishable=perishable,
            length=length,
            origin=origin,
            cancelled=cancelled,
        )

    def as_record(self) -> dict:
        return asdict(self)


def check_manifest(notice: Notice) -> None:
    if notice.perishable > notice.boxes:
        raise ValueError("冷藏箱数大于全部箱量")
    if notice.eta < notice.sent - 720:
        raise ValueError("ETA 已超出允许反拨窗口")
    if len(notice.imo) != 7 or not notice.imo.isdecimal():
        raise ValueError("船籍须为七位 IMO 号")
