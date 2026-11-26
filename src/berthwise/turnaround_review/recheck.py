from collections import defaultdict
from collections.abc import Mapping
from hashlib import sha256
from json import dumps
from dataclasses import asdict
from math import isfinite
from .contracts import PortAudit

def checksum(plans, windows, config):
    plan_rows=[asdict(p) for p in sorted(plans,key=lambda row:row.call)]
    evidence={key:[asdict(s) for s in sorted(items,key=lambda item:(item.berth,item.start,item.stop))]
              for key,items in windows.items()}
    return sha256(dumps([plan_rows,evidence,config],ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()


def _prediction_parts(value):
    if value is None:
        return None, False, True
    if isinstance(value,Mapping):
        manual=value.get("manual") is True or value.get("in_domain") is False
        for key in ("high","upper","upper_bound"):
            if key in value:
                raw=value[key]
                if isinstance(raw,(int,float)) and not isinstance(raw,bool) and isfinite(raw):
                    return float(raw), manual, True
        return None, manual, True
    manual=getattr(value,"manual",False) is True or getattr(value,"in_domain",True) is False
    for attr in ("high","upper","upper_bound"):
        if hasattr(value,attr):
            raw=getattr(value,attr)
            if isinstance(raw,(int,float)) and not isinstance(raw,bool) and isfinite(raw):
                return float(raw), manual, True
    if isinstance(value,(int,float)) and not isinstance(value,bool) and isfinite(value):
        return float(value), False, True
    return None, manual, True


def _scoped_prediction(mapping, record):
    for key in ((record.berth,record.cranes),record.berth,record.cranes,
                str(record.cranes),f"{record.berth}:{record.cranes}"):
        if key in mapping:
            return _prediction_parts(mapping[key])
    if "high" in mapping or "manual" in mapping or "upper" in mapping:
        return _prediction_parts(mapping)
    return None, False, False


def prediction_for(record, predictions):
    if predictions is None:
        return None, False, False
    if callable(predictions):
        for args in ((record.call,record.berth,record.cranes),
                     (record.call,record.cranes),(record.call,record.berth),(record.call,)):
            try:
                value=predictions(*args)
            except TypeError:
                continue
            return _prediction_parts(value)
        return None, False, False
    if not isinstance(predictions,Mapping):
        return None, False, False
    for key in ((record.call,record.berth,record.cranes),(record.call,record.berth),
                (record.call,record.cranes)):
        if key in predictions:
            return _prediction_parts(predictions[key])
    if record.call not in predictions:
        return None, False, False
    value=predictions.get(record.call)
    if value is None:
        return _prediction_parts(None)
    if isinstance(value,Mapping):
        return _scoped_prediction(value,record)
    return _prediction_parts(value)


def audit(plans, windows, config, predictions=None, **options):
    if predictions is None:
        for name in ("estimated","estimates","bounds","upper_bounds","forecasts","predicted_bounds"):
            if options.get(name) is not None:
                predictions=options[name]
                break
    if predictions is None and isinstance(config,Mapping):
        predictions=(config.get("predictions") or config.get("estimated")
                     or config.get("estimates") or config.get("bounds"))
    signature_config=dict(config) if isinstance(config,Mapping) else {"value":config}
    if predictions is not None:
        signature_config["predictions"]=(f"<callable:{getattr(predictions,'__name__','prediction')}>"
                                         if callable(predictions) else predictions)
    violations=[]
    assigned=defaultdict(list)
    for record in plans:
        if record.state!="安排靠泊":
            if any(v is not None for v in (record.berth,record.moor,record.sail)):
                violations.append({"code":"rejected_with_slot","call":record.call})
            continue
        if record.berth is None or record.moor is None or record.sail is None or record.moor>=record.sail:
            violations.append({"code":"assignment_incomplete","call":record.call})
            continue
        compatible=[row for row in windows.get(record.call,()) if row.berth==record.berth and
                    row.start<=record.moor<record.sail<=row.stop and row.cranes>=record.cranes]
        if not compatible:
            violations.append({"code":"outside_tide","call":record.call})
        if record.margin is None or record.margin<0:
            violations.append({"code":"underkeel","call":record.call})
        if predictions is None and getattr(record,"upper",None) is not None:
            upper,manual,found=_prediction_parts(record.upper)
        else:
            upper,manual,found=prediction_for(record,predictions)
        if found and manual:
            violations.append({"code":"prediction_out_of_domain","call":record.call})
        elif found and upper is not None:
            reserved=record.sail-record.moor
            if reserved+1e-9<upper:
                violations.append({"code":"reservation_too_short","call":record.call,
                                   "upper_bound":upper,"reserved_minutes":reserved})
        assigned[record.berth].append(record)
    busy=0
    wait=0
    for berth,records in sorted(assigned.items()):
        latest=None
        for item in sorted(records,key=lambda row:row.moor):
            if latest and item.moor<latest.sail:
                violations.append({"code":"berth_overlap","call":item.call,"earlier":latest.call,"berth":berth})
            if latest is None or item.sail>latest.sail:
                latest=item
            busy+=item.sail-item.moor
            wait+=item.wait or 0
    waiting=sum(record.state!="安排靠泊" for record in plans)
    return PortAudit(tuple(violations),busy,wait,waiting,checksum(plans,windows,signature_config))

def delayed_cost(orders, reefers, hourly_guarantee):
    if hourly_guarantee<0:
        raise ValueError("保障费率不可为负")
    return [{"call":row.call,"charge_cents":((row.wait or 0)*reefers.get(row.call,0)*hourly_guarantee+59)//60}
            for row in orders if row.state=="安排靠泊"]


def reconcile(plans, windows, config, predictions=None, **options):
    return audit(plans, windows, config, predictions, **options)
