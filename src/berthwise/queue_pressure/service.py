from .hazard import train_pressure, classify

def flag_queue(model, incoming, estimates, windows, at, yard):
    result={}
    for ship in incoming:
        slots=windows[ship.call]
        open_min=min((item.start for item in slots),default=at+300)
        queue_ahead=sum(other.eta<=ship.eta and other.call != ship.call for other in incoming)
        distinct=len({item.berth for item in slots if item.start <= max(at,ship.eta)+30})
        verdict=classify(model,queue_ahead,estimates[ship.call].high,distinct,max(0,open_min-ship.eta),yard)
        verdict.update(call=ship.call,anchor_queue=queue_ahead,berths=distinct)
        result[ship.call]=verdict
    return result
