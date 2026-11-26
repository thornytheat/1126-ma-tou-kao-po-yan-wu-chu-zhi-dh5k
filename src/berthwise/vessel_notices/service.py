from collections import defaultdict
from .revisions import Inbox, snapshot

def register_notices(raw_rows, cutoff):
    return snapshot(raw_rows, cutoff)

def line_workload(inbox: Inbox) -> list[dict]:
    hours = defaultdict(list)
    for row in inbox.active:
        hours[(row.eta//60,row.line)].append(row)
    output = []
    for (hr,line), ships in sorted(hours.items()):
        output.append({"hour":hr,"route":line,"ships":len(ships),
                       "boxes":sum(record.boxes for record in ships),
                       "reefer":sum(record.perishable for record in ships),
                       "draft_max":max(record.draft for record in ships)})
    return output
