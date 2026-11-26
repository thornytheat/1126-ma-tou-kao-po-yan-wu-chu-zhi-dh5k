from dataclasses import replace
import pytest
from berthwise.berth_assignment.contracts import Booking,AssignmentRequest
from berthwise.berth_assignment.planner import book
from berthwise.berth_assignment.switching import careful_blocks,switch_delta,try_exceptions
from berthwise.tide_slices.contracts import Opening
from berthwise.turnaround_review.handover_log import audit_actual,index_confirmed,MooringNote
from berthwise.pipeline import run

def booking(key="J9",**adjust):
    original=dict(call=key,berth="K1",moor=90,sail=150,wait=15,state="安排靠泊",reason="",
                  cranes=3,margin=.6)
    original.update(adjust)
    return Booking(**original)

def receipt(key="J9", **adjust):
    original=dict(call=key,berth="K1",sequence=1,moored=100,started=110,ended=145,departed=153,
                  cranes=3,signed=True,lifted=70,seal="桩簿-41")
    original.update(adjust)
    return original

def test_quay_switch_fee_counts_only_incremental_delay():
    before=[booking(),booking("K7",wait=40)]
    after=[booking("K7",wait=15),booking(berth="K2",wait=29)]
    summary=switch_delta(before,after,{"J9":8,"K7":15},400)
    first,last=summary
    assert first.call=="J9" and first.old_berth=="K1" and first.new_berth=="K2"
    assert first.extra_wait==14 and first.cost_cents==747
    assert last.extra_wait==-25 and last.cost_cents==0
    assert switch_delta(before,before,{},400)==()

def test_exceptions_reassign_but_never_remove_input_available_windows():
    slots=(Opening("K1",60,240,.7,3),Opening("K2",60,240,.6,2))
    request=AssignmentRequest("J9",60,50,9,False,False,slots,2,90)
    baseline=book([request],1)
    risk=try_exceptions([request],baseline,[{"name":"检修","reserved":{"K1":[[60,120],[100,140]]},"limit":1}],400)
    assert risk[0]["available"]==1 and risk[0]["rerouted"]==1
    assert risk[0]["calls"][0]["new_berth"]=="K2"
    assert baseline[0].berth=="K1" and request.windows==slots
    with pytest.raises(ValueError,match="递增"):
        careful_blocks([(120,100)])
    assert careful_blocks([(60,90),(90,105),(108,119)])==((60,105),(108,119))

def test_newly_staged_without_prior_wait_has_unknown_fee_delta():
    current=(booking(),)
    first=switch_delta([],current,{"J9":8},100)[0]
    assert first.old=="未入册"
    assert first.new=="安排靠泊" and first.extra_wait is None
    assert first.cost_cents==0 and first.affected_cold_boxes==8
    with pytest.raises(ValueError,match="重复"):
        switch_delta([],current*2,{},400)
    with pytest.raises(ValueError,match="负价"):
        switch_delta([],current,{},-4)

def test_quayside_throughput_uses_net_activity_and_cranes():
    record=booking()
    result=audit_actual([record],[receipt()],160)
    assert result[0]["switch"]=="在原泊位执行"
    assert result[0]["inbound_delta"]==10
    assert result[0]["efficiency"]==40
    assert result[0]["tally"]==70
    assert result[-1]=={"occupied_real_minutes":53,"occupied_plan_minutes_for_receipts":60}

@pytest.mark.parametrize(("edit","label"),[
    ({"berth":"Z9"},"现场换泊"),({"signed":False,"berth":"Z9"},"签报未签"),
    ({"moored":110},"进泊延误"),({"departed":185},"回执尚未结案"),
])
def test_quayside_receipts_distinguish_unapproved_and_late(edit,label):
    result=audit_actual([booking()],[receipt(**edit)],160)
    assert result[0]["switch"]==label
    assert result[0]["call"]=="J9"

def test_revisions_can_be_identical_or_conflicting_without_arbitrary_choice():
    current=receipt()
    revision=receipt(sequence=2,lifted=95)
    selected,issues=index_confirmed([current,revision,revision])
    assert issues==[] and selected["J9"].lifted==95
    selected,issues=index_confirmed([current,revision,dict(revision,lifted=94)])
    assert selected=={} and issues==[{"call":"J9","switch":"签报同效冲突"}]
    assert audit_actual([booking()],[current,revision,dict(revision,lifted=94)],160)[1]==issues[0]

def test_unplanned_cargo_does_not_change_reconciled_planned_totals():
    blocked=booking("Y8",berth=None,moor=None,sail=None,wait=None,state="继续候泊")
    rows=audit_actual([booking(),blocked],[receipt("Y8"),receipt("H9")],160)
    assert rows[0]=={"call":"J9","switch":"计划待回执"}
    assert rows[1]=={"call":"Y8","switch":"存在现场签报但无本计划"}
    assert rows[2]=={"call":"H9","switch":"无报港但有现场签报"}
    assert rows[-1]["occupied_real_minutes"]==0

@pytest.mark.parametrize("fault",[{"sequence":0},{"signed":3},{"lifted":-1},{"started":20},{"departed":21}])
def test_invalid_outturn_receipt_is_not_entered(fault):
    with pytest.raises(ValueError):
        MooringNote(**receipt(**fault))

def test_workbench_exposes_zero_ambiguity_around_event_and_actual_state():
    data=run()["stages"]
    assert any("blocked_minutes" in row for row in data[1]["records"])
    assert any(row.get("source_cutoff")==755 for row in data[2]["records"])
    assert any("fee_change_cents" in row for row in data[4]["records"])
    actual=data[5]["records"]
    assert any(row.get("switch")=="签报未签" for row in actual)
    assert any(row.get("occupied_real_minutes",0)>0 for row in actual)



def test_future_revised_port_receipt_cannot_hide_signed_previous_snapshot():
    original=receipt()
    revised=receipt(sequence=2,berth="Z3",departed=176,lifted=85)
    earlier=audit_actual([booking()],[original,revised],160)
    assert earlier==audit_actual([booking()],[original],160)
    assert earlier[0]["switch"]=="在原泊位执行" and earlier[0]["tally"]==70
    latest=audit_actual([booking()],[original,revised],176)
    assert latest[0]["switch"]=="现场换泊" and latest[0]["tally"]==85
    assert latest[-1]["occupied_real_minutes"] > earlier[-1]["occupied_real_minutes"]


def test_unrelated_dock_outage_does_not_disturb_prior_commitments():
    option=(Opening("K1",60,240,.76,3), Opening("K2",60,240,.57,3))
    calls=[AssignmentRequest("J9",60,57,12,True,False,option,2,100),
           AssignmentRequest("J10",90,58,8,False,False,option,1,100)]
    baseline=book(calls,3)
    candidate={"name":"远端风窗","reserved":{"K9":[[60,240]]},"limit":3}
    judgment=try_exceptions(calls,baseline,[candidate],400)[0]
    assert judgment=={"scenario":"远端风窗","available":2,"rerouted":0,
                      "fee_change_cents":0,"calls":[]}
    assert all(row.berth in {"K1","K2"} for row in baseline)


@pytest.mark.parametrize(("work_start","finish","cranes","boxes","rate"), [
    (105,135,2,85,85), (106,166,4,128,32), (100,130,3,76,50.67),
])
def test_quay_productivity_median_is_never_padded_with_idle_time(work_start,finish,cranes,boxes,rate):
    fact=receipt(started=work_start,ended=finish,departed=180,cranes=cranes,lifted=boxes)
    evaluation=audit_actual([booking()],[fact],180)
    assert evaluation[0]["efficiency"]==rate
    assert evaluation[0]["tally"]==boxes
    assert evaluation[-1]["occupied_real_minutes"]==80
    assert evaluation[-1]["occupied_plan_minutes_for_receipts"]==60


def test_unknown_reefer_quantities_do_not_charge_without_inventory():
    original=booking(wait=10)
    revised=booking(wait=23)
    change=switch_delta([original],[revised],{},600)[0]
    assert change.extra_wait==13 and change.affected_cold_boxes==0
    assert change.cost_cents==0
    with pytest.raises(ValueError,match="冷藏箱数"):
        switch_delta([original],[revised],{"J9":-2},600)
