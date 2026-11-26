import json
from dataclasses import asdict
from pathlib import Path
from .tide_slices.wind_windows import adjust_weather
from .dwell_estimator.backtesting import compare_k, readable
from .queue_pressure.calibration_review import replay_outcomes
from .berth_assignment.switching import try_exceptions
from .turnaround_review.handover_log import audit_actual
from .vessel_notices.service import register_notices, line_workload
from .tide_slices.service import plan_from_hydro, summarize_windows
from .dwell_estimator.service import learn, estimate_all, duration_evidence
from .queue_pressure.service import train_pressure, flag_queue
from .berth_assignment.service import requests, book, committed_blocks
from .turnaround_review.service import finalize, check_records, outcome_groups

SAMPLE = Path(__file__).resolve().parents[2] / "sample_data"

def load(name):
    return json.loads((SAMPLE / name).read_text(encoding="utf-8"))

def run(capacity: int | None=None) -> dict:
    cap = 7 if capacity is None else capacity
    if type(cap) is not int or not 1<=cap<=100:
        raise ValueError("排靠航次数应在 1 至 100")
    controls=load("sector_controls.json")
    controls["capacity"]=cap
    moment=controls["at"]
    past=load("completed_calls.json")
    inbox=register_notices(load("pilot_notices.json"),moment)
    fleet=inbox.active
    windows=plan_from_hydro(fleet,load("harbor_tidal_bulletin.json"),controls["berths"],moment,controls["horizon"])
    constraints=load("pilot_wind_forecasts.json")
    windows,weather_notes=adjust_weather(windows,constraints["reports"],constraints["policy"],moment)
    prior_error=readable(compare_k(past,[(620,755),(755,890)]))
    model=learn(past,moment)
    estimated=estimate_all(model,fleet,windows,controls["yard"])
    queue_labels=load("anchorage_outcomes.json")
    pressure_replay=train_pressure(queue_labels,controls["training_cutoff"]-110,controls["training_cutoff"])
    queue_accuracy=replay_outcomes(pressure_replay,queue_labels,controls["training_cutoff"],moment)
    pressure=train_pressure(queue_labels,controls["training_cutoff"],moment)
    risks=flag_queue(pressure,fleet,estimated,windows,moment,controls["yard"])
    applications=requests(fleet,estimated,risks,windows)
    assignments=book(applications,cap)
    audit,bills=finalize(assignments,windows,fleet,controls)
    downtime=try_exceptions(applications,assignments,load("quay_incidents.json"),controls["reefer_fee"])
    transfer=audit_actual(assignments,load("signed_outturn_logs.json"),controls["horizon"]+120)
    linked={ship.call:ship for ship in fleet}
    groups=outcome_groups(assignments)
    rows=[]
    for booking in assignments:
        ship=linked[booking.call]
        line=asdict(booking)
        line.update(route=ship.line, boxes=ship.boxes, reefers=ship.perishable,
                    high=estimated[booking.call].high,risk=risks[booking.call]["risk"],
                    reason=booking.reason+" · "+risks[booking.call]["reason"])
        rows.append(line)
    series=[{"label":"接收申报","value":len(inbox.events)},
            {"label":"正式航次","value":len(fleet)},
            {"label":"有潮窗","value":sum(bool(parts) for parts in windows.values())},
            {"label":"可自动评估","value":sum(not app.manual for app in applications)},
            {"label":"已排靠泊","value":sum(bool(x.berth) for x in assignments)}]
    return {
        "metrics":{"开放航次":len(fleet),"已排靠泊":groups.get("安排靠泊",0),
                   "待处理航次":audit.waiting,"等泊总分钟":audit.wait_minutes},
        "columns":{"call":"航次","route":"航线","boxes":"箱量","reefers":"冷藏箱",
                   "high":"占泊上界分","risk":"候泊概率","berth":"泊位","moor":"靠泊分钟",
                   "wait":"候泊分钟","state":"处置","reason":"证据"},
        "rows":rows,
        "series":series,
        "stages":[
            {"title":"报港去重","summary":f"有效航次 {len(fleet)} 个，保留撤港及同权冲突证据",
             "records":[*inbox.events,*line_workload(inbox)]},
            {"title":"潮汐切片","summary":f"共 {sum(map(len,windows.values()))} 段安全泊位窗口",
             "records":summarize_windows(windows)+weather_notes},
            {"title":"滞港估计","summary":f"参考 {len(model.references)} 个结案航次",
             "records":duration_evidence(estimated,model)+prior_error},
            {"title":"候泊风险","summary":f"使用 {pressure.rows} 条早期结案拟合和后续结案校准",
             "records":list(risks.values())+queue_accuracy},
            {"title":"靠泊调配","summary":f"本截面配额 {cap}，泊位已登记 {len(committed_blocks(assignments))} 个",
             "records":[asdict(row) for row in assignments]+downtime},
            {"title":"滞港复核","summary":"安全窗与泊位占用检查通过" if audit.cleared else "发现靠泊安全冲突",
             "records":check_records(audit,bills)+transfer},
        ],
    }
