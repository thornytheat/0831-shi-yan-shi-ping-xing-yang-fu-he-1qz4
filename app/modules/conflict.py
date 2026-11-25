"""跨委托记录号比对。

同一记录号被两个及以上委托引用、且原始测值（concentration）不一致时，
涉事记录标记为存疑；同号同值视为不同委托各自的平行数据，不算冲突。
存疑不影响同委托内其余样品的正常交付。
"""
from collections import defaultdict


def cross_conflicts(rows):
    readings = defaultdict(dict)
    for row in rows:
        if row['kind'] == 'control':
            continue
        readings[row['record']].setdefault(row['entrust'], set()).add(row['concentration'])

    conflicts = {}
    for record, by_entrust in readings.items():
        if len(by_entrust) < 2:
            continue
        values = {value for readings_set in by_entrust.values() for value in readings_set}
        if len(values) > 1:
            conflicts[record] = {
                'record': record,
                'entrusts': sorted(by_entrust),
                'values': {entrust: sorted(values_set) for entrust, values_set in sorted(by_entrust.items())},
            }
    return conflicts


def doubtful_samples(case_rows, conflicts):
    """把存疑记录号折算到该业务组的样品号，供交付件逐样标注。"""
    sample_records = defaultdict(list)
    for row in case_rows:
        if row['kind'] != 'control':
            sample_records[row['sample']].append(row['record'])
    return {str(sample): sorted({record for record in records if record in conflicts})
            for sample, records in sorted(sample_records.items(), key=lambda item: int(item[0]))
            if any(record in conflicts for record in records)}
