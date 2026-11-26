from collections import defaultdict
from dataclasses import dataclass
from .contracts import Notice, check_manifest

SOURCE_WEIGHT = {"船代": 10, "港调": 20, "值班复核": 30}

@dataclass(frozen=True, slots=True)
class Inbox:
    active: tuple[Notice, ...]
    events: tuple[dict, ...]

    def counts(self) -> dict[str, int]:
        summary = defaultdict(int)
        for event in self.events:
            summary[event["status"]] += 1
        return dict(summary)

def content_key(row):
    return (row.imo,row.line,row.eta,row.draft,row.boxes,row.perishable,row.length,row.cancelled)

def choose(rows):
    version = max(row.revision for row in rows)
    highest = max(SOURCE_WEIGHT.get(row.origin,0) for row in rows if row.revision == version)
    candidates = [row for row in rows if row.revision == version and SOURCE_WEIGHT.get(row.origin,0) == highest]
    if len({content_key(row) for row in candidates}) > 1:
        return None, "同权信息冲突", version
    chosen = max(candidates,key=lambda row:(row.sent,row.origin))
    return (None,"已撤港",version) if chosen.cancelled else (chosen,"启用",version)

def snapshot(raw_rows, cutoff):
    groups = defaultdict(list)
    events = []
    for row in raw_rows:
        try:
            record = Notice.parse(row)
            check_manifest(record)
        except (TypeError,ValueError) as error:
            events.append({"call":row.get("call","?"),"status":"隔离","message":str(error)})
            continue
        if record.sent > cutoff:
            events.append({"call":record.call,"status":"到达晚于本次截面","minute":record.sent})
            continue
        groups[record.call].append(record)
    active = []
    for key, items in sorted(groups.items()):
        current,status,rev = choose(items)
        events.append({"call":key,"status":status,"revision":rev,"reports":len(items)})
        if current is not None:
            active.append(current)
    events.sort(key=lambda row:(row["call"],row["status"],str(row)))
    return Inbox(tuple(active),tuple(events))
