import pytest
from berthwise.dwell_estimator.neighbors import learn, predict_dwell, weighted_quantile

def completion(k,**updates):
    raw=dict(call=f"K{k}",line="T",arrived=k*10,closed=k*10+12,boxes=200+k*5,reefer=.1,
             draft=8.+k*.3,cranes=3,yard=.5,duration=58+5*k,late=bool(k%2))
    raw.update(updates)
    return raw

def study(**settings):
    return learn([completion(i) for i in range(7)],90,**settings)

def test_late_closure_excluded():
    # TRAP-42 学习仅用实际结案且早于截面的作业结果。
    data=[completion(i) for i in range(7)]
    model=learn(data,90)
    newer=completion(8,closed=90,draft=25,duration=900)
    assert learn(data+[newer],90)==model
    assert len(learn(data+[newer],91).references)==8

def test_constant_robust_spread():
    # TRAP-32 常数分量的 MAD 为零时分母须落在工程下限。
    saved=study()
    assert saved.scale[1]==.03 and saved.scale[3]==.05
    assert saved.distance(saved.midpoint,saved.midpoint)==0

def test_weighted_reference_quantile():
    points=[(50,4),(100,1),(80,1),(30,2)]
    assert weighted_quantile(points,.5)==50
    assert weighted_quantile(points,.9)==100
    with pytest.raises(ValueError):
        weighted_quantile([(2,0)],.5)

def test_stable_neighbors_and_calibrated_bounds():
    # TRAP-44 邻域太远时，即使有有限分位数，也须降为人工核对。
    model=study(count=5)
    ordinary=predict_dwell(model,"T",211,.1,8.6,3,.5)
    unusual=predict_dwell(model,"Q",4900,.9,14,3,.5)
    assert not ordinary.manual and unusual.manual
    assert ordinary.high>=ordinary.expected
    assert unusual.distance>ordinary.distance

def test_reorder_input_does_not_move_fit():
    rows=[completion(i) for i in range(7)]
    assert learn(rows,90)==learn(reversed(rows),90)
    one=predict_dwell(learn(rows,90),"T",205,.1,8,3,.5)
    assert one.neighbors[0]=="K0"

def test_prediction_is_batch_invariant():
    # TRAP-53 邻居按训练窗口冻结，拼入异常大船不会改掉同批其他估计。
    saved=study()
    normal=("T",175,.11,8.6,3,.5)
    outputs=[predict_dwell(saved,*args) for args in [normal,("X",800,.7,17,2,.8),normal]]
    assert outputs[0]==outputs[2]==predict_dwell(saved,*normal)
    assert outputs[0]!=outputs[1]

def test_model_validates_waterfields():
    with pytest.raises(ValueError):
        learn([completion(0,draft=float("inf"))],90)
    with pytest.raises(ValueError,match="重复结案"):
        learn([completion(0),completion(0)],90)

def test_small_calibration_group():
    model=learn([completion(0),completion(2)],90,count=5)
    assert predict_dwell(model,"T",200,.1,8,3,.5).manual
    with pytest.raises(ValueError,match="训练窗"):
        learn([completion(5)],30)
