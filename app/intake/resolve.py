from collections import defaultdict


def _key(row):
    return row['entrust'], row['record']


def partition(candidates):
    """同一委托内记录键唯一；不同委托共用记录号是合法情形，交由委托交付阶段比对。"""
    by_key = defaultdict(list)
    for line, row in candidates:
        by_key[_key(row)].append((line, row))
    accepted, rejected = [], []
    for (entrust, record), entries in by_key.items():
        first = entries[0][1]
        if any(row != first for _, row in entries):
            rejected.extend({'line': line, 'record': record, 'case': row['case'],
                             'entrust': entrust, 'reason': 'DUPLICATE_CONFLICT'}
                            for line, row in entries)
            continue
        accepted.append(first)
        rejected.extend({'line': line, 'record': record, 'case': row['case'],
                         'entrust': entrust, 'reason': 'DUPLICATE_REPLAY'}
                        for line, row in entries[1:])
    return accepted, rejected
