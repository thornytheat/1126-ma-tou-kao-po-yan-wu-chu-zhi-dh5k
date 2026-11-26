import pytest
from berthwise.tide_slices.contracts import Opening
from berthwise.tide_slices.wind_windows import WeatherHold, WindPolicy, accepted_notices, across_berth, blocked_weather, intersect_wind_slot, adjust_weather

def notice(**changes):
    pieces=dict(key="WK",harbor="信号塔",begin=75,end=105,issued=50,gust_kn=35,visibility_m=1000,
                wind_from=90,level=1,revoked=False)
    pieces.update(changes)
    return pieces

def profile(**changes):
    data=dict(standard_heading=0,cross_limit=28,min_visibility=900,installation="信号塔")
    data.update(changes)
    return data

def test_safe_harbor_revisions_only_use_visible_data():
    initial=notice()
    lifted=notice(level=2,revoked=True,issued=81)
    assert accepted_notices([initial,lifted],80)=={"信号塔":(WeatherHold(**initial),)}
    assert accepted_notices([initial,lifted],81)=={}
    assert accepted_notices([lifted,initial],80)==accepted_notices([initial,lifted],80)

def test_notice_conflict_cannot_select_wind_direction_arbitrarily():
    reports=[notice(),notice(wind_from=80)]
    with pytest.raises(ValueError,match="冲突"):
        accepted_notices(reports,70)
    assert len(accepted_notices([notice(),notice()],70)["信号塔"])==1

@pytest.mark.parametrize(("from_angle","axis","fraction"),[(0,0,0),(359,179,0),(90,0,1),(30,0,.5),(210,0,.5),(310,10,3**.5/2)])
def test_relative_wind_direction_uses_perpendicular_component(from_angle,axis,fraction):
    assert across_berth(33,from_angle,axis)==pytest.approx(33*fraction,abs=1e-10)

@pytest.mark.parametrize(("raw_changes","codes"),[
    ({},("横风",)), ({"gust_kn":13,"visibility_m":830},("能见度",)),
    ({"visibility_m":800},("横风","能见度")), ({"gust_kn":28,"visibility_m":900},()),
])
def test_regulatory_decision_is_strict_at_wind_and_visibility_limits(raw_changes,codes):
    output=blocked_weather([WeatherHold(**notice(**raw_changes))],WindPolicy(**profile()))
    if not codes:
        assert output==()
    else:
        assert output[0]["reasons"]==codes
        assert output[0]["notice"]=="WK"
        assert output[0]["end"]-output[0]["begin"]==30

def test_cutout_leaves_adjacent_quarters_and_tidal_margin():
    before=Opening("R",45,150,.45,3)
    report={"begin":75,"end":105}
    after=intersect_wind_slot(before,[report],15)
    assert after==(Opening("R",45,75,.45,3),Opening("R",105,150,.45,3))
    assert sum(row.stop-row.start for row in after)==75
    assert intersect_wind_slot(before,[{"begin":40,"end":151}],15)==()

def test_weather_limits_are_installed_per_berth_not_global():
    opened={"P":(Opening("N",45,140,.5,2),Opening("S",45,140,1.1,3))}
    raw=[notice(begin=76,end=103)]
    status,events=adjust_weather(opened,raw,{"N":profile(),"S":profile(standard_heading=90)},70)
    assert status["P"][-1]==opened["P"][-1]
    assert [(x.start,x.stop) for x in status["P"][:2]]==[(45,75),(105,140)]
    assert events==[{"call":"P","berth":"N","blocked_minutes":30,"notices":["WK"]}]
    assert len(opened["P"])==2

@pytest.mark.parametrize("changes",[{"gust_kn":-3},{"wind_from":360},{"visibility_m":-10},{"level":0},{"end":60}])
def test_corrupt_wind_notice_rejected(changes):
    with pytest.raises(ValueError):
        WeatherHold(**notice(**changes))
