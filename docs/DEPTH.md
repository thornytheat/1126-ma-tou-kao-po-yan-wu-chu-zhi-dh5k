# 码头靠泊延误处置 · 验证索引

AI/ML / 传统ML · 集装箱靠港时长预测、候泊超时与靠泊调配

## 功能模块

| 模块 | 业务职责 | 计算规则 | 核心位置 | 独立测试 |
|---|---|---|---|---|
| M1 | 报港去重 | 按报港版次和审签权限解析航次，保留迟到、撤港及冲突轨迹 | `src/berthwise/vessel_notices/revisions.py` `src/berthwise/vessel_notices/contracts.py` `src/berthwise/vessel_notices/service.py` | `tests/test_vessel_notices.py` |
| M2 | 潮汐切片 | 按最近发布潮位作半开安全窗，端点净余水深、维修与船长限值共同筛除 | `src/berthwise/tide_slices/clearance.py` `src/berthwise/tide_slices/contracts.py` `src/berthwise/tide_slices/service.py` | `tests/test_tide_slices.py` |
| M3 | 滞港估计 | 冻结历史 MAD 尺度，按航线与作业负载加权近邻估算占泊上下界 | `src/berthwise/dwell_estimator/neighbors.py` `src/berthwise/dwell_estimator/contracts.py` `src/berthwise/dwell_estimator/service.py` | `tests/test_dwell_estimator.py` |
| M4 | 候泊风险 | 带惩罚二分类拟合靠泊超时，留出折做平滑分桶校准并拦截异常工况 | `src/berthwise/queue_pressure/hazard.py` `src/berthwise/queue_pressure/contracts.py` `src/berthwise/queue_pressure/service.py` | `tests/test_queue_pressure.py` |
| M5 | 靠泊调配 | 按冷藏、紧急与承诺窗口分派，潮位净余排序并维护逐泊位不可重叠预留 | `src/berthwise/berth_assignment/planner.py` `src/berthwise/berth_assignment/contracts.py` `src/berthwise/berth_assignment/service.py` | `tests/test_berth_assignment.py` |
| M6 | 滞港复核 | 独立复核泊位占用冲突和净水深，量化等泊分钟及冷藏箱保障支出 | `src/berthwise/turnaround_review/recheck.py` `src/berthwise/turnaround_review/contracts.py` `src/berthwise/turnaround_review/service.py` | `tests/test_turnaround_review.py` |

## 边界案例

| 陷阱 | 触发 | 错误做法 | 实现 | 位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-19 | 同版不同来源的申报冲突 | 顺序覆盖 | 依来源权限取报港记录 | `src/berthwise/vessel_notices/revisions.py` | `tests/test_vessel_notices.py::test_source_precedence` |
| TRAP-23 | 整点刚好结束维修 | 双闭区间 | 半开占用 | `src/berthwise/tide_slices/clearance.py` | `tests/test_tide_slices.py::test_closed_endpoint` |
| TRAP-25 | 同版水文发报冲突 | 任取最后值 | 冲突航窗隔离 | `src/berthwise/tide_slices/clearance.py` | `tests/test_tide_slices.py::test_revision_conflict` |
| TRAP-31 | 极端候泊 logit | 直接 exp 导致溢出 | 分支稳定 sigmoid | `src/berthwise/queue_pressure/hazard.py` | `tests/test_queue_pressure.py::test_stable_logistic` |
| TRAP-32 | 历史堆场恒定导致零 MAD | 按零散布做距离归一 | 工程噪音下限 | `src/berthwise/dwell_estimator/neighbors.py` | `tests/test_dwell_estimator.py::test_constant_robust_spread` |
| TRAP-42 | 延迟标签在未来结案 | 全量近邻查询 | 严格按实际结案时点纳入 | `src/berthwise/dwell_estimator/neighbors.py` | `tests/test_dwell_estimator.py::test_late_closure_excluded` |
| TRAP-43 | 训练折全负 | 概率除零或高置信误读 | 平滑校准及少类稳定拟合 | `src/berthwise/queue_pressure/hazard.py` | `tests/test_queue_pressure.py::test_all_negative_fold` |
| TRAP-44 | 极端吃水和箱量工况 | 直接接收近邻分位数 | 距离拒绝自动放行 | `src/berthwise/dwell_estimator/neighbors.py` | `tests/test_dwell_estimator.py::test_stable_neighbors_and_calibrated_bounds` |
| TRAP-53 | 批次追加异常大船 | 批归一改变其他位置 | 推断尺度只读取拟合结果 | `src/berthwise/dwell_estimator/neighbors.py` | `tests/test_dwell_estimator.py::test_prediction_is_batch_invariant` |
| TRAP-54 | 预报或计划粒度变化 | 复用陈旧复核 | 配置与输入内容共同签名 | `src/berthwise/turnaround_review/recheck.py` | `tests/test_turnaround_review.py::test_deterministic_fingerprint_and_upstream_key` |
