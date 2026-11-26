from math import ceil
from collections import defaultdict
from .contracts import AssignmentRequest
from .planner import book

def requests(ships, estimate, risk, windows, bounds=None, **options):
    if bounds is None:
        for name in ("upper_bounds","candidate_bounds","predictions","estimates"):
            if options.get(name) is not None:
                bounds=options[name]
                break
    output=[]
    for ship in ships:
        stay=estimate[ship.call]
        probability=risk[ship.call]
        # Candidate-specific out-of-domain crane estimates are handled by the
        # planner when bounds are supplied.  Without them, retain the original
        # whole-voyage model-domain gate.
        dwell_manual=stay.manual if bounds is None else False
        requested=AssignmentRequest(ship.call,ship.eta,ceil(stay.high),ship.perishable,
                                    probability["urgent"],dwell_manual or not probability["in_domain"],
                                    windows[ship.call],1 if ship.boxes<200 else 2,
                                    90 if ship.perishable>25 else 150)
        output.append(requested)
    return tuple(output)

def committed_blocks(bookings):
    blocks=defaultdict(list)
    for order in bookings:
        if order.berth and order.moor is not None and order.sail is not None:
            blocks[order.berth].append((order.moor,order.sail,order.call))
    return {key:tuple(sorted(lines)) for key,lines in sorted(blocks.items())}
