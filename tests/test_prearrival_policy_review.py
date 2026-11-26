from math import isfinite,log
import pytest
from berthwise.queue_pressure.calibration_review import (
    precision_recall_pairs,cross_entropy,error_table,replay_outcomes,
)
from berthwise.queue_pressure.hazard import train_pressure
from berthwise.pipeline import run

def observation(i,**extra):
    item=dict(call=f"新沪-{100+i}",phase="引航站南" if i%3 else "引航站北",queue=i%15,dwell=60+i%10*9,
              free=1+i%4,open_delay=10+i%17*7,yard=.42+i%9*.045,late=i%4>1,
              closed=i*10+8,severe=i%8==0)
    item.update(extra)
    return item

def batch():
    return [observation(ix) for ix in range(55)]

def test_tied_score_uses_one_joint_conservative_precision_step():
    scored=[(.9,True),(.9,False),(.5,True),(.2,False)]
    score,curve=precision_recall_pairs(scored)
    assert score==pytest.approx((1/2+2/3)/2)
    assert curve[0]=={"cut":.9,"precision":.5,"recall":.5,"selected":2}
    assert curve[-1]["precision"]==.5 and curve[-1]["recall"]==1
    assert precision_recall_pairs(scored[::-1])==(score,curve)

def test_no_positive_curve_keeps_negative_counts_and_undefined_recall():
    score,curve=precision_recall_pairs([(.81,False),(.02,False),(.32,False)])
    assert score is None and len(curve)==3
    assert all(row["precision"]==0 and row["recall"] is None for row in curve)
    assert precision_recall_pairs([])==(None,[])

@pytest.mark.parametrize(("prob","truth"),[(0,1),(1,0),(0,0),(1,1)])
def test_cross_entropy_stays_finite_at_logit_probability_bounds(prob,truth):
    result=cross_entropy([(prob,truth)])
    assert isfinite(result) and result>=0
    assert (result>20)==(prob!=truth)
    assert cross_entropy([]) is None

def test_out_of_domain_flags_go_to_human_review_not_calibration():
    decisions=[dict(risk=.12,raw=.02,actual=False,in_domain=True),
               dict(risk=.18,raw=.14,actual=True,in_domain=False),
               dict(risk=.84,raw=.9,actual=True,in_domain=True)]
    report,curve=error_table("湾东",decisions,.8)
    assert report.rows==3 and report.coverage==pytest.approx(2/3)
    assert report.positive==2 and report.flagged==2 and report.missed==0
    assert report.brier==pytest.approx((.12**2+.16**2)/2)
    assert report.weighted_shift==pytest.approx((.1-.06)/2)
    assert report.cross_entropy==pytest.approx((-log(.88)-log(.84))/2)
    assert sum(item["selected"]==2 for item in curve)==1

def test_phase_reports_union_without_future_visible_label_count():
    history=batch()
    fitted=train_pressure(history,250,300)
    changes=[observation(99,closed=450),observation(100,closed=940)]
    caps=(.2,.5,.9)
    first=replay_outcomes(fitted,history,300,450,caps)
    second=replay_outcomes(fitted,history+changes,300,450,caps)
    assert first==second
    for threshold in caps:
        result=[row for row in first if row["operating_cut"]==threshold]
        union=next(row for row in result if row["phase"]=="所有航区")
        assert union["rows"]==15
        assert union["rows"]==sum(row["rows"] for row in result if row is not union)
        assert union["missed"]<=union["positive"]
    counts=[row["flagged"] for row in first if row["phase"]=="所有航区"]
    assert counts[0]>=counts[1]>=counts[2]

def test_replay_accepts_exact_lower_boundary_and_rejects_duplicates():
    history=batch()
    model=train_pressure(history,250,300)
    lower=observation(98,closed=300)
    status=replay_outcomes(model,history+[lower],300,301,(.5,))
    assert next(row for row in status if row["phase"]=="所有航区")["rows"]==1
    with pytest.raises(ValueError,match="重复"):
        replay_outcomes(model,[lower,lower],300,301,(.5,))

@pytest.mark.parametrize(("since","until","targets"),[(300,300,[.5]),(350,300,[.5]),(300,450,[.5,.5]),(300,450,[-.5])])
def test_invalid_replay_thresholds_denied(since,until,targets):
    model=train_pressure(batch(),250,300)
    with pytest.raises(ValueError):
        replay_outcomes(model,batch(),since,until,targets)

def test_application_publishes_policy_comparison_with_holdout_cases():
    readings=run()["stages"][3]["records"]
    data=[row for row in readings if row.get("phase")=="所有航区"]
    assert [row["operating_cut"] for row in data]==[.45,.64,.8]
    assert all(row["rows"]>0 and 0<=row["flagged"]<=row["rows"] for row in data)
    assert any(row["average_precision"] is not None for row in data)
