from app.business import DomainIssue
from app.intake.service import inspect
from app.modules.calculate import compute
from app.modules.conflict import cross_conflicts, doubtful_samples
from app.modules.grouping import case_groups
from app.modules.policy import policy
from app.modules.prepare import prepare
from app.modules.reconcile import balance


def evaluate(entrust, case_id, rows, stage, conflicts):
    case = {'case': case_id, 'entrust': entrust,
            'records': [r['record'] for r in rows], 'status': 'READY'}
    case['sources'] = [{key: row[key] for key in ('record', 'kind', 'sample', 'concentration',
                                                   'lod', 'loq', 'limit')} for row in rows]
    case['doubtful'] = doubtful_samples(rows, conflicts)
    try:
        case['prep'], payload = prepare(rows)
        if stage >= 3:
            case['measure'] = compute(payload)
        if stage >= 4:
            case.update(policy(case['measure']))
    except DomainIssue as error:
        case['status'] = error.code
    return case


def run(data, stage=5):
    intake = inspect(data)
    output = {'intake': {k: v for k, v in intake.items() if k != 'rows'}}
    if stage == 1:
        return output
    conflicts = cross_conflicts(intake['rows'])
    output['conflicts'] = sorted(conflicts.values(), key=lambda item: item['record'])
    cases = [evaluate(entrust, case_id, rows, stage, conflicts)
             for (entrust, case_id), rows in case_groups(intake['rows'])]
    output['cases'] = cases
    if stage >= 5:
        output['balance'] = balance(intake, cases, conflicts)
    return output
