"""按委托组装复核交付件。

交付边界：
- 只包含该委托自己的样品、记录与证据，不出现别家委托的任何记录；
- 不携带批次总数、其他委托数量、全批放行状态等整批信息；
- 客户可凭原始测值与判定参数自行复算；
- 跨委托同记录号测值冲突的样品标 ``DOUBTFUL``，同委托其余样品照常交付；
- 旧批缺少原始测值时保留当时结论并标明 ``CANNOT_RECALCULATE``，不向新批借数。
"""
from app.config import RULE_VERSION

PACKAGE_SCHEMA = 'entrust-delivery/1'


def _sample_evidence(case):
    pairs = case.get('measure', {}).get('evidence', {}).get('pairs', {})
    result = {}
    for sample, info in pairs.items():
        result[sample] = dict(info)
    return result


def _current_samples(case):
    evidence = _sample_evidence(case)
    rows = [row for row in case['sources'] if row['kind'] != 'control']
    samples = sorted({row['sample'] for row in rows}, key=int)
    doubtful = case.get('doubtful', {})
    items = []
    for sample in samples:
        own = [row for row in rows if row['sample'] == sample]
        entry = {
            'sample': str(sample),
            'records': sorted(row['record'] for row in own),
            'readings': [{'record': row['record'], 'kind': row['kind'],
                          'concentration': row['concentration']} for row in own],
            'method': _method_bounds(own),
            'recalculable': True,
        }
        verdict = evidence.get(str(sample))
        entry['verdict'] = dict(verdict) if verdict else None
        if str(sample) in doubtful:
            entry['status'] = 'DOUBTFUL'
            entry['doubtful_records'] = doubtful[str(sample)]
        elif verdict is None:
            entry['status'] = 'HELD'
        else:
            entry['status'] = 'PASS' if verdict['pass'] else 'HELD'
        items.append(entry)
    return items


def _method_bounds(rows):
    head = rows[0]
    return {'lod': head['lod'], 'loq': head['loq']}


def _legacy_samples(case):
    """旧批没有原始测值：只回放当时结论，禁止用新批数据补齐。"""
    evidence = _sample_evidence(case)
    doubtful = case.get('doubtful', {})
    items = []
    for sample, verdict in evidence.items():
        entry = {
            'sample': str(sample),
            'records': [],
            'readings': [],
            'method': None,
            'recalculable': False,
            'status': 'DOUBTFUL' if sample in doubtful else
                      ('PASS' if verdict['pass'] else 'HELD'),
            'verdict': dict(verdict),
            'note': 'CANNOT_RECALCULATE',
        }
        if sample in doubtful:
            entry['doubtful_records'] = doubtful[sample]
        items.append(entry)
    return items


def build_package(report, entrust):
    own_cases = [case for case in report['cases'] if case['entrust'] == entrust]
    if not own_cases:
        return None

    samples, held, doubtful, recalculable = [], 0, 0, 0
    conflict_records = set()
    for case in own_cases:
        has_sources = bool(case.get('sources'))
        entries = _current_samples(case) if has_sources else _legacy_samples(case)
        for entry in entries:
            entry['case'] = case['case']
            if entry['recalculable']:
                recalculable += 1
            if entry['status'] == 'DOUBTFUL':
                doubtful += 1
                conflict_records.update(entry.get('doubtful_records', ()))
            elif entry['status'] == 'HELD':
                held += 1
            samples.append(entry)

    controls = []
    for case in own_cases:
        for row in case.get('sources', []):
            if row['kind'] == 'control':
                controls.append({'case': case['case'], 'rpd_limit_bp': row['limit'],
                                 'absolute_limit': row['loq']})

    return {
        'schema': PACKAGE_SCHEMA,
        'rule_version': RULE_VERSION,
        'entrust': entrust,
        'run_id': report['manifest']['run_id'],
        'created': report['manifest']['created'],
        'scope': 'ENTRUST_ONLY',
        'samples': samples,
        'controls': controls,
        'conflicts': sorted(conflict_records),
        'totals': {'samples': len(samples), 'recalculable': recalculable,
                   'doubtful': doubtful, 'held': held},
    }


def entrusts_of(report):
    return sorted({case['entrust'] for case in report['cases']})
