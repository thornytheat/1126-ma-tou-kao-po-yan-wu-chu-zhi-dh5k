from math import isfinite
import pytest
from berthwise.queue_pressure.hazard import expit, features, train_pressure, classify, raw_score

def sample(i, **settings):
    data=dict(call=f"Q{i}",phase="A",queue=i%9,dwell=50+7*(i%6),free=1+i%3,
              open_delay=10+(i*13)%50,yard=.4+((i*11)%30)/100,late=i%3!=0,closed=11*i+1,severe=i%6==0)
    data.update(settings)
    return data

def fit():
    return train_pressure([sample(i) for i in range(30)],230,340)

def test_stable_logistic():
    # TRAP-31 exp(-x) for a large negative x overflows; branched shape remains finite.
    assert expit(-1000)==0 and expit(1000)==1
    assert expit(12)==pytest.approx(1-expit(-12))
    assert expit(0)==.5

def test_severe_positives_change_fitted_loss():
    dataset=[sample(i) for i in range(30)]
    original=train_pressure(dataset,230,340)
    weighted=train_pressure([dict(row,severe=row["late"]) for row in dataset],230,340)
    assert original.coefficients != weighted.coefficients
    assert original.center==weighted.center

def test_unknown_history_missing():
    with pytest.raises(ValueError):
        train_pressure([],120,120)
    with pytest.raises(ValueError):
        train_pressure([sample(3)],130,100)

def test_future_and_holdout_separate():
    baseline=fit()
    changed=train_pressure([sample(i,late=False) if i>20 else sample(i) for i in range(30)],230,340)
    assert baseline.center==changed.center and baseline.coefficients==changed.coefficients
    assert baseline.calibrated != changed.calibrated

def test_all_negative_fold():
    # TRAP-43 候泊训练无正例不隐含准确的高风险概率，返回有限的平滑概率。
    result=train_pressure([sample(i,late=False) for i in range(30)],230,340)
    decision=classify(result,3,72,2,14,.53)
    assert isfinite(decision["risk"]) and 0<=decision["risk"]<.64
    assert decision["raw"]<=.5

def test_abnormal_port_pressure():
    model=fit()
    normal=classify(model,2,78,1,25,.55)
    outlier=classify(model,42,850,0,5500,.99)
    assert normal["in_domain"] and not outlier["in_domain"]
    assert outlier["urgent"] and outlier["reason"]=="超出训练工况"

def test_load_adjusted_by_berth_count():
    plain=features(8,120,0,40,.5)
    open_ports=features(8,120,3,40,.5)
    assert plain[0]==8 and open_ports[0]==2
    assert plain[1:]==open_ports[1:]

def test_monotone_expit_and_calibration_finite():
    model=fit()
    values=[mapping[1] for mapping in model.calibrated]
    assert len(values)==5 and all(0<=entry<=1 for entry in values)
    assert 0<=raw_score(model,features(3,90,2,45,.5))<=1
