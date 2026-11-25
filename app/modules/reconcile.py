from collections import Counter


def balance(intake, cases, conflicts=None):
    conflicts = conflicts or {}
    accounted = intake['accepted'] + intake['rejected'] + intake['blank'] + intake['repeated']
    status = Counter(case['status'] for case in cases)
    ready = status.pop('READY', 0)
    observed = sum(len(case['records']) for case in cases)
    doubtful_records = set(conflicts)
    entrusts = sorted({case.get('entrust') for case in cases if case.get('entrust')})
    return dict(input=intake['input'], accepted=intake['accepted'], isolated=intake['rejected'],
                ignored=intake['blank'] + intake['repeated'], accounted=accounted,
                balanced=accounted == intake['input'] and observed == intake['accepted'],
                ready=ready, pending=len(cases)-ready, issues=dict(sorted(status.items())),
                entrusts=entrusts, entrust_count=len(entrusts), doubtful=len(doubtful_records),
                releasable=bool(cases) and ready == len(cases) and not intake['rejected']
                and accounted == intake['input'] and observed == intake['accepted'])
