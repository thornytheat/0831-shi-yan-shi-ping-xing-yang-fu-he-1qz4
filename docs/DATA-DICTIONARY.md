# 字段与业务定义

输入编码 UTF-8，允许 BOM。首行必须匹配样例列顺序。记录键、业务组和委托号保留原始字符串。`kind` 允许 primary, duplicate, control。说明列 `note` 可以跨行，限制 200 字。

列顺序：`record, case, entrust, kind, sample, concentration, lod, loq, limit, note`。`entrust` 为委托号，标识样品归属的委托；同一记录号可被不同委托引用，记录键的唯一性按 `(entrust, record)` 判定。

业务字段按 `sample`、`concentration`、`lod`、`loq`、`limit` 排列。最终值单位见阶段结果。数字接受非负整数、全角数字和完整千分位。空串、短横线、N/A、NULL 与未知为缺值。无关字段用 0 占位。

浓度整数为微克每升。双方低于检出限标为共同未检出；一侧低于检出限进人工复核。双方均达到 5 倍定量限时用相对偏差，其余用绝对差。用整数交叉积比较边界，显示值按基点向下取整。

`incoming.csv` 含两个委托（WT-A、WT-B）：WT-A 保留四个业务组，第二组提供不同边界，第三组触发业务拒收，第四组需要核对；WT-B 的 0005 组与 WT-A 共用记录号 000201 但测值不同，触发跨委托存疑。另含重复表头、同委托冲突记录、重复回放与错误列数。`ready.csv` 含可以签发的一个委托、两个组。

## 委托交付件字段

`GET /api/runs/<id>/deliveries/<entrust>` 返回 `entrust-delivery/1`：

| 字段 | 含义 |
|---|---|
| `entrust` | 本件归属委托，整包不出现其他委托标识 |
| `scope` | 固定 `ENTRUST_ONLY`，不含整批放行状态、批次总数或别家记录 |
| `samples[].readings` | 该样品在本委托下的原始测值与记录号，供客户自行复算 |
| `samples[].method` | 检出限/定量限参数；旧批缺原始测值时为 `null` |
| `samples[].recalculable` | `false` 表示无法复算，保留当时结论并标注 `CANNOT_RECALCULATE` |
| `samples[].status` | `PASS`、`HELD` 或 `DOUBTFUL`（跨委托同号测值冲突） |
| `samples[].doubtful_records` | 触发存疑的记录号清单 |
| `controls` | 本委托各组的判定限值 |
| `totals` | 仅统计本委托的样品数、可复算数、存疑数与暂缓数 |

