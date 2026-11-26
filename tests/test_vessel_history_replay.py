from dataclasses import replace
from types import SimpleNamespace
from statistics import mean
import pytest
from berthwise.dwell_estimator.backtesting import compare_k,interval_width,readable,rolling_labels,summaries
from berthwise.dwell_estimator.neighbors import learn,predict_dwell

def settled(i, **changes):
    values=dict(call=f"石-74{i:02d}",line=("沪一" if i % 2 else "洋山"),arrived=17*i,closed=17*i+35,
                boxes=170+14*i,reefer=(i*7%15)/100,draft=8.+(i%5)*.3,cranes=1+i%2,
                yard=.51+(i%3)*.08,duration=47+i*4,late=False)
    values.update(changes)
    return values

def docket():
    return [settled(i) for i in range(26)]

def test_rolling_backtest_never_labels_inputs_at_or_after_horizon():
    records=docket()
    split=(155,278)
    first=compare_k(records,[split],(5,7))
    horizon_record=settled(26,closed=477,boxes=5200,duration=1490)
    second=compare_k(records+[horizon_record],[split],(5,7))
    assert first==second
    labels=rolling_labels(records,*split)
    assert all(split[0]<=row.closed<split[1] for row in labels)
    for kind in ("k=5","k=7"):
        real=next(item for item in first if item.label==kind and item.group=="整体")
        assert real.support==len(labels)
        assert real.source_cutoff==split[0]

def test_predict_dwell_and_group_report_match_independent_arithmetic():
    table=docket()
    cutoff,until=180,340
    model=learn(table,cutoff,count=5)
    holdout=rolling_labels(table,cutoff,until)
    samples=[]
    widths=[]
    for log in holdout:
        forecast=predict_dwell(model,log.line,log.boxes,log.reefer,log.draft,log.cranes,log.yard)
        samples.append(abs(log.duration-forecast.expected))
        widths.append(log.duration<=forecast.high)
    got=next(item for item in compare_k(table,[(cutoff,until)],(5,)) if item.group=="整体")
    assert got.mae_minutes==pytest.approx(mean(samples))
    assert got.share_covered==pytest.approx(mean(widths))
    assert got.support==len(holdout)
    rendered=next(row for row in readable((got,)) if row["group"]=="整体")
    assert rendered["mae_minutes"]==round(got.mae_minutes,4)

def test_no_holdout_keeps_identifiable_route_without_a_numeric_score():
    records=[settled(0),settled(3)]
    report=compare_k(records,[(200,250)],(1,))
    assert {row.group for row in report}=={"沪一","洋山","整体"}
    for item in report:
        assert item.support==item.manual_count==0
        assert item.share_covered is None and item.bias_minutes is None
        assert readable([item])[0]["average_slip"] is None

@pytest.mark.parametrize(("observed","covered","slip","offset"),[(50,1,0,-5),(55,1,0,0),(70,1,0,15),(73,0,3,18)])
def test_coverage_and_wait_magnitude_have_different_boundaries(observed,covered,slip,offset):
    guess=SimpleNamespace(high=70,expected=55,manual=True)
    measured=interval_width(guess,observed)
    assert measured=={"covered":covered,"slip":slip,"center":offset,"manual":1}

def test_report_shapes_do_not_share_arbitrary_neighbor_configurations():
    records=docket()
    actual=compare_k(records,[(180,210),(240,260)],(3,7))
    assert {(row.source_cutoff,row.label) for row in actual}=={(180,"k=3"),(180,"k=7"),(240,"k=3"),(240,"k=7")}
    assert actual==compare_k(records[::-1],[(180,210),(240,260)],(3,7))
    with pytest.raises(ValueError,match="互异"):
        compare_k(records,[(180,260)],(3,3))
    with pytest.raises(ValueError,match="观察"):
        rolling_labels(records,220,200)
