from dataclasses import replace
import pytest
from berthwise.turnaround_review.recheck import audit,delayed_cost,checksum
from berthwise.berth_assignment.contracts import Booking
from berthwise.tide_slices.contracts import Opening

def assigned(key="D1", **fields):
    row=dict(call=key,berth="Q",moor=45,sail=90,wait=15,state="安排靠泊",reason="done",cranes=3,margin=.7)
    row.update(fields)
    return Booking(**row)

def tides(*keys):
    return {key:(Opening("Q",30,180,.8,4),) for key in keys}

def test_deterministic_fingerprint_and_upstream_key():
    # TRAP-54 调入一次水文变更须改变复核快照，打乱输入顺序不改变签名。
    rows=[assigned(),assigned("H",moor=90,sail=150)]
    slots=tides("D1","H")
    assert checksum(rows,slots,{"grain":15})==checksum(rows[::-1],slots,{"grain":15})
    assert checksum(rows,slots,{"grain":15})!=checksum(rows,slots,{"grain":30})
    slots["D1"]=(Opening("Q",45,180,.8,4),)
    assert checksum(rows,slots,{"grain":15})!=checksum(rows,tides("D1","H"),{"grain":15})

def test_normal_audit_counts_work():
    rows=[assigned(),assigned("H",moor=90,sail=150,wait=22)]
    result=audit(rows,tides("D1","H"),{})
    assert result.cleared and result.dock_minutes==105 and result.wait_minutes==37

def test_detect_cascading_overlap():
    a=assigned(sail=150)
    rows=[a,assigned("K",moor=60,sail=90),assigned("H",moor=90,sail=120)]
    result=audit(rows,tides("D1","K","H"),{})
    assert not result.cleared and [r["earlier"] for r in result.conflicts]==["D1","D1"]

def test_reject_outside_window_or_below_keel():
    result=audit([assigned(moor=15,margin=-.02)],tides("D1"),{})
    assert {r["code"] for r in result.conflicts}=={"outside_tide","underkeel"}

def test_reject_partial_or_suspended_assignment():
    rows=[assigned(sail=None),assigned("H",state="继续候泊")]
    result=audit(rows,tides("D1","H"),{})
    assert result.waiting==1 and result.dock_minutes==0
    assert {r["code"] for r in result.conflicts}=={"assignment_incomplete","rejected_with_slot"}

def test_reefer_cost_integer_cents():
    costs=delayed_cost([assigned(wait=13)],{"D1":11},20)
    assert costs==[{"call":"D1","charge_cents":48}]
    assert delayed_cost([assigned(state="调度")],{"D1":11},20)==[]

def test_fee_configuration_validation():
    with pytest.raises(ValueError):
        delayed_cost([],{},-1)
    assert delayed_cost([assigned()],{},20)[0]["charge_cents"]==0

def test_empty_shift_total():
    state=audit([],{}, {})
    assert state.cleared and state.waiting==0
    assert state.dock_minutes==0 and state.wait_minutes==0
