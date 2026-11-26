import json
import pytest
from berthwise.pipeline import run

def test_yard_plan_complete_and_deterministic():
    result=run()
    assert result==run()
    assert len(result["stages"])==6 and len(result["rows"])>=10
    assert result["stages"][-1]["records"][0]["passed"]
    json.dumps(result,allow_nan=False)

def test_capacity_moves_pending_units():
    small=run(1)
    ample=run(12)
    assert small["metrics"]["已排靠泊"]==1
    assert ample["metrics"]["已排靠泊"]>1
    assert small["stages"][-1]["records"][0]["digest"]!=ample["stages"][-1]["records"][0]["digest"]

def test_untrusted_manifest_does_not_join_registry():
    result=run()
    seen={row.get("status") for row in result["stages"][0]["records"]}
    assert {"已撤港","同权信息冲突","隔离"}<=seen
    assert not any(row["call"]=="PAC-无效" for row in result["rows"])

def test_total_dock_minutes_from_committed_rows():
    result=run()
    committed=[row for row in result["rows"] if row["berth"]]
    total=sum(row["sail"]-row["moor"] for row in committed)
    assert total==result["stages"][-1]["records"][0]["dock_minutes"]

def test_bad_override_stops_before_compute():
    for override in (0,101,False,2.1):
        with pytest.raises(ValueError,match="航次"):
            run(override)
