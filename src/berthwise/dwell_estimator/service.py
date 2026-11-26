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

def crane_upper_bounds(learning, active, windows, yard):
    """Candidate bounds keyed by the actual crane count of each tide opening."""
    bounds={}
    for ship in active:
        by_cranes={}
        crane_counts={item.cranes for item in windows[ship.call]}
        for crane_count in sorted(crane_counts):
            estimate=predict_dwell(learning,ship.line,ship.boxes,ship.perishable/ship.boxes,
                                  ship.draft,crane_count,yard)
            by_cranes[crane_count]={"high":estimate.high,"manual":estimate.manual,
                                    "distance":estimate.distance,"support":estimate.support}
        bounds[ship.call]=by_cranes
    return bounds

def duration_evidence(results, model):
    return [dict(asdict(row),call=call,training_calls=len(model.references)) for call,row in results.items()]
