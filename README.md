# 码头靠泊延误处置

面向码头调度的本地工作台。内置业务样例覆盖集装箱靠港时长预测、候泊超时与靠泊调配。样例采用确定性构造，适合复现实验和核查边界行为。

## 启动

```sh
docker compose up --build -d
```

打开 `http://127.0.0.1:18205/` 查看靠泊调度单。左侧六个入口可展开运行证据。调整「靠泊名额（个）」，点击「重算靠泊」比较处置结果。结束后执行 `docker compose down --remove-orphans`。

## 独立业务模块

- 报港去重 `vessel_notices`
- 潮汐切片 `tide_slices`
- 滞港估计 `dwell_estimator`
- 候泊风险 `queue_pressure`
- 靠泊调配 `berth_assignment`
- 滞港复核 `turnaround_review`

## 查看运行结果

- `GET /api/overview` 返回默认运行及其指纹。
- `POST /api/scenario` 接收 `{"capacity": 3}`。入口接受 1–100 的整数，应用样例时使用该业务额度。
- `GET /api/stages/turnaround_review` 查看该环节的独立证据，支持 `?capacity=3`。

```sh
docker compose exec -T app python -m berthwise.delivery evaluate --capacity 3
docker compose exec -T app pytest -q
```

数据和模型约定见 [业务契约](docs/SPEC.md)。模块、例外规则与验证入口见 [业务深度](docs/DEPTH.md)。
