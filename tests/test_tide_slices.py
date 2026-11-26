from types import SimpleNamespace
import pytest
from berthwise.tide_slices.contracts import Berth, TideSample, Opening
from berthwise.tide_slices.clearance import forecast_index, least_depth, windows, overlaps

def berth(**values):
    base=dict(key="D2",length=240,chart_depth=10.2,underkeel=.6,cranes=3,closed=())
    base.update(values)
    return Berth(**base)

def ship(**values):
    base=dict(call="W7",eta=30,draft=9.6,length=210)
    base.update(values)
    return SimpleNamespace(**base)

def guide(time, reading=.1, **updates):
    meta=dict(minute=time,depth=reading,source="南港",issued=0,revision=1,caution=False)
    meta.update(updates)
    return TideSample(**meta)

def test_closed_endpoint():
    # TRAP-23 相邻维修窗按半开区间处理。
    assert not overlaps((30,45),(45,60))
    index={30:(0,False),45:(0,False),60:(0,False),75:(0,False)}
    assert windows(index,berth(closed=((45,60),)),ship(),30,75)==(Opening("D2",30,45,0,3),Opening("D2",60,75,0,3))

def test_revision_conflict():
    # TRAP-25 同一发布版冲突时隔离该段潮位。
    events=[guide(30,.2),guide(30,.4)]
    assert forecast_index(events,3)=={}
    assert forecast_index(events+[guide(30,.65,issued=1,revision=2)],3)=={30:(.65,False)}

def test_unsafe_gap_rejected():
    index={0:(2,False),15:(3,True),30:(2,False),45:(1,False)}
    assert least_depth(index,0,30,15) is None
    assert least_depth(index,30,45,15)==1
    assert least_depth(index,45,60,15) is None

def test_both_edges_safety_margin():
    index={30:(.1,False),45:(-.2,False),60:(.1,False)}
    assert windows(index,berth(),ship(),30,60)==()
    narrow=windows(index,berth(),ship(draft=9.3),30,60)
    assert narrow[0].tide_margin==.1

def test_length_allowance():
    index={30:(3,False),45:(3,False)}
    assert not windows(index,berth(),ship(length=226),30,45)
    assert windows(index,berth(),ship(length=225),30,45)[0].stop==45

def test_published_forecast_only():
    current=forecast_index([guide(30),guide(30,.4,issued=8,revision=2)],7)
    assert current=={30:(.1,False)}
    assert forecast_index([guide(30,caution=True)],7)[30][1]

def test_invalid_configuration():
    with pytest.raises(ValueError,match="重叠"):
        berth(closed=((0,50),(30,80)))
    with pytest.raises(ValueError,match="对齐"):
        least_depth({},3,45,15)

def test_arrival_rounded_to_grid():
    index={30:(1,False),45:(1,False),60:(1,False)}
    candidate=windows(index,berth(),ship(eta=31),30,60)
    assert candidate==(Opening("D2",45,60,1,3),)
