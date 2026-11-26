import pytest
from berthwise.berth_assignment.contracts import AssignmentRequest
from berthwise.berth_assignment.planner import first_vacancy, book
from berthwise.tide_slices.contracts import Opening

def job(name="T9",**extra):
    base=dict(call=name,eta=60,expected=48,cold_boxes=10,urgent=False,manual=False,
              windows=(Opening("S2",60,300,.8,3),),cranes_needed=2,max_wait=100)
    base.update(extra)
    return AssignmentRequest(**base)

def test_takes_earliest_nonoverlapping_landing():
    opening=Opening("K",30,300,.5,3)
    assert first_vacancy(opening,[(60,90),(114,139)],62,51)==(150,210)
    assert first_vacancy(opening,[(120,160)],60,60)==(60,120)
    assert first_vacancy(opening,[(30,300)],30,55) is None

def test_bids_break_on_berth_margin():
    windows=(Opening("M",60,300,.8,4),Opening("K",60,300,.5,3))
    assert book([job(windows=windows)],3)[0].berth=="M"
    earlier=Opening("J",45,300,.4,3)
    assert book([job(eta=40,windows=windows+(earlier,))],3)[0].berth=="J"

def test_urgent_reefer_has_precedence():
    q=[job("Z",cold_boxes=0),job("P",urgent=True,cold_boxes=0),job("Y",urgent=True,cold_boxes=1)]
    output=book(q,1)
    assert output==book(reversed(q),1)
    assert output[0].call=="Y" and output[0].berth=="S2"
    assert output[1].state=="下一批排靠"

def test_outside_model_preempts_capacity():
    result=book([job("Z",manual=True,urgent=True),job("H")],1)
    assert result[0].state=="人工复核" and result[1].state=="安排靠泊"
    assert result[0].moor is None

def test_crane_requirement_blocks_unsafe_shortcuts():
    one=Opening("C",60,300,1.,1)
    short=Opening("P",60,75,1.,3)
    assert book([job(windows=(one,short))],3)[0].state=="继续候泊"

def test_maximum_cold_wait():
    only=Opening("X",180,420,.7,3)
    result=book([job(windows=(only,),max_wait=60)],3)
    assert result[0].state=="协调改港"
    assert book([job(windows=(only,),max_wait=120)],3)[0].wait==120

def test_reservation_snapshot_not_mutated():
    blocked={"S2":[(60,120)]}
    result=book([job("Y"),job("Z",eta=90)],3,blocked)
    assert blocked=={"S2":[(60,120)]}
    assert result[0].moor==120 and result[1].moor==180

def test_duplicate_errors():
    with pytest.raises(ValueError):
        book([job(),job()],2)
    with pytest.raises(ValueError):
        book([job()],0)
