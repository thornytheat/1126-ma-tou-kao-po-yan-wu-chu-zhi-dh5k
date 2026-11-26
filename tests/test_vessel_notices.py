import pytest
from berthwise.vessel_notices.contracts import Notice, check_manifest
from berthwise.vessel_notices.revisions import snapshot
from berthwise.vessel_notices.service import line_workload

def row(**values):
    facts = dict(call="X2",imo="9005003",line="A",revision=1,sent=500,eta=580,draft=9.5,
                 boxes=250,perishable=30,length=215,origin="船代",cancelled=False)
    facts.update(values)
    return facts

def test_source_precedence():
    # TRAP-19 同版冲突先使用人工审核等级，再看发送时点。
    data=[row(draft=9),row(origin="港调",draft=10),row(origin="值班复核",draft=11)]
    assert snapshot(data,515).active[0].draft == 11
    assert snapshot(data,515) == snapshot(data[::-1],515)

def test_clock_and_revision():
    # TRAP-42 截面晚到不影响同一时刻能航次。
    data=[row(),row(revision=2,sent=550,eta=620)]
    assert snapshot(data,549).active[0].eta == 580
    assert snapshot(data,550).active[0].eta == 620

def test_tied_conflict_quarantined():
    result=snapshot([row(eta=598),row(eta=600)],580)
    assert not result.active
    assert result.counts()=={"同权信息冲突":1}

def test_withdrawal():
    result=snapshot([row(),row(revision=2,cancelled=True)],580)
    assert result.active == ()
    assert result.counts()=={"已撤港":1}

def test_manifest_business_totals():
    with pytest.raises(ValueError,match="箱数"):
        check_manifest(Notice.parse(row(perishable=451)))
    with pytest.raises(ValueError,match="IMO"):
        check_manifest(Notice.parse(row(imo="FR22")))

def test_grouped_workload():
    result=snapshot([row(),row(call="RX",boxes=301,perishable=50),row(call="WA",line="B")],580)
    totals=line_workload(result)
    assert totals[0]["boxes"]==551
    assert totals[0]["reefer"]==80
    assert totals[1]["ships"]==1

def test_blank_and_types():
    assert snapshot([row(call=" ")],590).counts()=={"隔离":1}
    assert snapshot([row(draft=True)],590).counts()=={"隔离":1}
    assert snapshot([row(sent=5.5)],590).counts()=={"隔离":1}

def test_duplicate_idempotence():
    data=[row(),row(),row(sent=510)]
    result=snapshot(data,590)
    assert len(result.active)==1
    assert result.active[0].sent==510
    assert result.events[0]["reports"]==3
