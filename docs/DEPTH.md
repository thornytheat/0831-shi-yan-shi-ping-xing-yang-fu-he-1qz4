# 实验室平行样复核规则登记

- 规模：中型

## 功能模块

| 模块 | 动作 | 接口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 样例采信 | 预览并定位坏行 | `POST /api/stages/intake` | `app/intake/service.py` | `tests/test_intake.py` |
| M2 样本配对 | 检查领域约束 | `POST /api/stages/prepare` | `app/modules/prepare.py` | `tests/test_prepare.py` |
| M3 偏差计算 | 查看业务计算结果 | `POST /api/stages/calculate` | `app/modules/calculate.py` | `tests/test_calculate.py` |
| M4 质控判定 | 查看签收判定 | `POST /api/stages/policy` | `app/modules/policy.py` | `tests/test_policy.py` |
| M5 运行对账 | 对照输入、采信和隔离行 | `POST /api/stages/balance` | `app/modules/reconcile.py` | `tests/test_reconcile.py` |
| M6 批次复核 | 执行批次并签发或暂缓 | `POST /api/runs、PATCH /api/runs/<id>` | `app/review/service.py` | `tests/test_review.py` |
| M7 证据交付 | 下载整批复核清单（内部） | `GET /api/runs/<id>/evidence` | `app/evidence/render.py` | `tests/test_evidence.py` |
| M8 委托交付 | 按委托出件、跨委托冲突标存疑、授权撤回 | `GET /api/runs/<id>/deliveries/<entrust>`、`POST .../withdraw` | `app/delivery/package.py`、`app/delivery/service.py` | `tests/test_delivery.py`、`tests/test_delivery_http.py` |

## 输入陷阱

| 编号 | 规则 | 处理 | 测试 |
|---|---|---|---|
| TRAP-02 | 去除 BOM | `app/intake/reader.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-03 | 按逻辑记录读取引号内换行 | `app/intake/reader.py` | `tests/test_intake.py::test_quoted_newline_is_one_logical_record` |
| TRAP-04 | 重复表头计入忽略行 | `app/intake/service.py` | `tests/test_intake.py::test_repeated_header_is_counted` |
| TRAP-05 | 异常列数隔离 | `app/intake/schema.py` | `tests/test_intake.py::test_extra_column_is_isolated` |
| TRAP-06 | 归一化全角数字和千分位 | `app/intake/numeric.py` | `tests/test_intake.py::test_full_width_and_grouping_are_canonical` |
| TRAP-07 | 空值行隔离 | `app/intake/numeric.py` | `tests/test_intake.py::test_sentinel_keeps_row_out_of_total` |
| TRAP-08 | 记录键保留前导零 | `app/intake/schema.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-14 | 同委托冲突版本都进入隔离；跨委托同号测值冲突改标存疑 | `app/intake/resolve.py`、`app/modules/conflict.py` | `tests/test_intake.py::test_duplicate_conflict_removes_both_copies`、`tests/test_delivery.py::test_same_record_different_entrusts_are_both_accepted` |
| TRAP-16 | 引号未闭合时拒收文件 | `app/intake/reader.py` | `tests/test_intake.py::test_unclosed_quote_invalidates_source` |
| TRAP-18 | 区分空文件、全空白和仅表头 | `app/intake/reader.py` | `tests/test_intake.py::test_empty_states_have_distinct_causes` |
| TRAP-26 | 拒绝旧版本复核 | `app/review/store.py` | `tests/test_review.py::test_review_optimistic_lock` |
| TRAP-31 | 委托交付件不得夹带别家记录或批次总数 | `app/delivery/package.py` | `tests/test_delivery.py::test_delivery_contains_only_own_entrust_data` |
| TRAP-32 | 撤回先入账则并发下载必拒 | `app/delivery/service.py`、`app/review/store.py` | `tests/test_delivery.py::test_concurrent_race_never_serves_download_after_revocation` |
| TRAP-33 | 旧批缺原测值保留结论并标无法复算，禁止新批补数 | `app/delivery/package.py` | `tests/test_delivery.py::test_legacy_package_keeps_verdict_but_flags_cannot_recalculate` |

## 领域反例

浓度整数为微克每升。双方低于检出限标为共同未检出；一侧低于检出限进人工复核。双方均达到 5 倍定量限时用相对偏差，其余用绝对差。用整数交叉积比较边界，显示值按基点向下取整。

`sample_data/incoming.csv` 的 0003 组触发预检异常，0004 组触发业务判定；WT-B 的 0005 组与 WT-A 共用记录号 000201 且测值不同，触发跨委托存疑，同组第二个样品照常交付。`tests/test_calculate.py` 还核对逐组结论和证据字段。
