# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean` 或 `file=<CSV>` 三选一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批和当前复核状态。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。

`GET /api/runs/<id>/evidence` 下载内含运行清单、行号隔离、业务证据和复核信息的 JSON（内部整批证据，不面向客户）。

## 按委托交付

`GET /api/runs/<id>/deliveries/<entrust>` 下载单个委托的复核交付件（`entrust-delivery/1`）。交付件只含该委托自己的样品、原始测值、判定参数和结论，可由客户自行复算；不含其他委托的记录、委托清单或批次总数。同记录号在两个委托下测值冲突时，涉事样品标 `DOUBTFUL`，同委托其余样品照常出件。旧批缺原始测值时保留当时结论并标 `CANNOT_RECALCULATE`，不用新批补数。委托不属于该批次返回 404 `ENTRUST_UNKNOWN`。

`POST /api/runs/<id>/deliveries/<entrust>/withdraw` 撤回该委托的交付授权（幂等）。撤回先入账后，随后的下载返回 403 `AUTH_REVOKED`；撤回与下载并发时以数据库事务先后为准，撤回提交后的任何下载都不会成功。撤回只影响指定委托，其他委托的交付件不受影响。
