from .contracts import TideSample, Berth
from .clearance import forecast_index, windows

def plan_from_hydro(vessels, forecasts, positions, at, until):
    hydro=forecast_index((TideSample.parse(row) for row in forecasts), at)
    berths=tuple(Berth(**dict(row,closed=tuple(map(tuple,row["closed"])))) for row in positions)
    if len({berth.key for berth in berths}) != len(berths):
        raise ValueError("泊位编号重复")
    return {ship.call:tuple(choice for berth in berths for choice in windows(hydro,berth,ship,at,until))
            for ship in vessels}

def summarize_windows(openings):
    result=[]
    for call, slots in openings.items():
        if not slots:
            result.append({"call":call,"status":"无安全潮窗"})
        else:
            for slot in slots:
                result.append({"call":call,"berth":slot.berth,"from":slot.start,"until":slot.stop,
                               "under_keel":slot.tide_margin,"cranes":slot.cranes})
    return result
