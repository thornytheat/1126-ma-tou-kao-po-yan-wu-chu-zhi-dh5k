from collections import Counter
from .recheck import audit, delayed_cost

def finalize(bookings, windows, notices, controls, predictions=None, **options):
    if predictions is None:
        for name in ("estimated","estimates","bounds","upper_bounds","forecasts"):
            if options.get(name) is not None:
                predictions=options[name]
                break
    control_sum={"issued":controls["at"],"limit":controls["capacity"],"equipment":controls["berths"]}
    evidence=audit(bookings, windows, control_sum, predictions)
    bills=delayed_cost(bookings,{item.call:item.perishable for item in notices},controls["reefer_fee"])
    return evidence,bills

def check_records(result, bills):
    return [{"passed":result.cleared,"dock_minutes":result.dock_minutes,
             "total_wait":result.wait_minutes,"unresolved":result.waiting,
             "digest":result.run_digest},*result.conflicts,*bills]

def outcome_groups(bookings):
    counts=Counter(row.state for row in bookings)
    return {key:counts[key] for key in sorted(counts)}
