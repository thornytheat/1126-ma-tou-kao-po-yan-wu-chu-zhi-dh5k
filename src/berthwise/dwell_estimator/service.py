from dataclasses import asdict
from .neighbors import learn, predict_dwell, weighted_quantile

def estimate_all(learning, active, windows, yard):
    records={}
    for ship in active:
        breakdown=windows[ship.call]
        crane_count=max((item.cranes for item in breakdown),default=2)
        records[ship.call]=predict_dwell(learning,ship.line,ship.boxes,ship.perishable/ship.boxes,
                                         ship.draft,crane_count,yard)
    return records

def duration_evidence(results, model):
    return [dict(asdict(row),call=call,training_calls=len(model.references)) for call,row in results.items()]
