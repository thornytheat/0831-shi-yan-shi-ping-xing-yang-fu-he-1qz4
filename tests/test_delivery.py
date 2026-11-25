"""按委托交付复核件的规则测试。

覆盖：同号测值冲突标存疑、同委托其他样品照常交付、交付边界不泄露别家数据、
旧批无法复算保留原结论、撤回授权先入账则拒绝下载（含并发）。
"""
import json

import pytest

from app.business import DomainIssue
from app.config import RULE_VERSION
from app.delivery.package import build_package
from app.delivery.service import deliver, withdraw
from app.intake.service import inspect
from app.review.service import execute
from conftest import csv_data


def _two_entrust_rows():
    return [
        # WT-A：两个样品，样品 1 的记录号与 WT-B 撞号且测值冲突
        ['A01', 'C1', 'WT-A', 'primary', '1', '100', '2', '10', '0', '委托甲'],
        ['A02', 'C1', 'WT-A', 'duplicate', '1', '110', '2', '10', '0', '委托甲'],
        ['A03', 'C1', 'WT-A', 'primary', '2', '11', '2', '10', '0', '委托甲'],
        ['A04', 'C1', 'WT-A', 'duplicate', '2', '14', '2', '10', '0', '委托甲'],
        ['A05', 'C1', 'WT-A', 'control', '0', '0', '0', '5', '1000', '委托甲质控'],
        # WT-B：同样引用 A01 记录号但测值不同；另含一个干净样品
        ['A01', 'C2', 'WT-B', 'primary', '1', '8', '2', '10', '0', '委托乙'],
        ['B02', 'C2', 'WT-B', 'duplicate', '1', '9', '2', '10', '0', '委托乙'],
        ['B03', 'C2', 'WT-B', 'primary', '2', '50', '2', '10', '0', '委托乙'],
        ['B04', 'C2', 'WT-B', 'duplicate', '2', '51', '2', '10', '0', '委托乙'],
        ['B05', 'C2', 'WT-B', 'control', '0', '0', '0', '5', '1000', '委托乙质控'],
    ]


@pytest.fixture
def two_entrust():
    return csv_data(_two_entrust_rows())


@pytest.fixture
def run_two(store, two_entrust):
    return execute(store, two_entrust)


# ---------- TRAP-14 在委托维度下的语义 ----------

def test_same_record_same_entrust_conflict_is_isolated(two_entrust):
    rows = _two_entrust_rows()
    rows.append(['A01', 'C1', 'WT-A', 'primary', '1', '999', '2', '10', '0', '同委托改测'])
    result = inspect(csv_data(rows))
    assert result['reasons']['DUPLICATE_CONFLICT'] == 2
    assert all(item['entrust'] == 'WT-A' for item in result['isolation']
               if item['reason'] == 'DUPLICATE_CONFLICT')


def test_same_record_different_entrusts_are_both_accepted(run_two):
    assert len(run_two['report']['conflicts']) == 1
    conflict = run_two['report']['conflicts'][0]
    assert conflict['record'] == 'A01' and conflict['entrusts'] == ['WT-A', 'WT-B']


def test_same_record_same_value_across_entrusts_is_not_conflict():
    rows = _two_entrust_rows()
    rows[5][5] = '100'  # WT-B 的 A01 改成与 WT-A 同测值
    from app.modules.pipeline import run
    assert run(csv_data(rows))['conflicts'] == []


def test_conflict_ignores_control_rows_and_dedupes_entrusts():
    from app.modules.conflict import cross_conflicts
    rows = [
        {'record': 'R1', 'entrust': 'E1', 'kind': 'primary', 'concentration': 5},
        {'record': 'R1', 'entrust': 'E2', 'kind': 'duplicate', 'concentration': 6},
        {'record': 'R9', 'entrust': 'E1', 'kind': 'control', 'concentration': 0},
        {'record': 'R9', 'entrust': 'E2', 'kind': 'control', 'concentration': 9},
    ]
    conflicts = cross_conflicts(rows)
    assert set(conflicts) == {'R1'}
    assert conflicts['R1']['entrusts'] == ['E1', 'E2']
    assert conflicts['R1']['values'] == {'E1': [5], 'E2': [6]}


def test_doubtful_samples_maps_record_to_sample_within_case():
    from app.modules.conflict import doubtful_samples
    case_rows = [
        {'record': 'R1', 'kind': 'primary', 'sample': 1},
        {'record': 'R2', 'kind': 'duplicate', 'sample': 1},
        {'record': 'R3', 'kind': 'primary', 'sample': 2},
    ]
    assert doubtful_samples(case_rows, {'R2': {}}) == {'1': ['R2']}


# ---------- 存疑隔离在样品级，同委托其他样品照常 ----------

def test_conflict_marks_only_involved_samples_doubtful(run_two):
    case_b = next(c for c in run_two['report']['cases'] if c['entrust'] == 'WT-B')
    assert case_b['doubtful'] == {'1': ['A01']}
    package = build_package(run_two['report'], 'WT-B')
    by_sample = {item['sample']: item for item in package['samples']}
    assert by_sample['1']['status'] == 'DOUBTFUL'
    assert by_sample['1']['doubtful_records'] == ['A01']
    assert by_sample['2']['status'] == 'PASS'
    assert package['totals'] == {'samples': 2, 'recalculable': 2, 'doubtful': 1, 'held': 0}


def test_doubtful_sample_keeps_own_readings_for_recalculation(run_two):
    package = build_package(run_two['report'], 'WT-A')
    sample_one = next(item for item in package['samples'] if item['sample'] == '1')
    assert sample_one['recalculable'] is True
    assert {r['concentration'] for r in sample_one['readings']} == {100, 110}
    assert sample_one['verdict']['mode'] == 'RPD'


# ---------- 交付边界：别家记录与批次总数不得出现 ----------

def test_delivery_contains_only_own_entrust_data(run_two):
    package = build_package(run_two['report'], 'WT-A')
    blob = json.dumps(package, ensure_ascii=False)
    assert 'WT-B' not in blob and 'C2' not in blob
    assert all(item['case'] == 'C1' for item in package['samples'])
    assert {c['case'] for c in package['controls']} == {'C1'}
    assert package['scope'] == 'ENTRUST_ONLY' and package['schema'] == 'entrust-delivery/1'
    assert package['rule_version'] == RULE_VERSION
    forbidden = {'balance', 'releasable', 'accepted', 'rejected', 'input', 'entrust_count'}
    assert forbidden.isdisjoint(package) and 'totals' in package


def test_unknown_entrust_is_rejected(store, run_two):
    with pytest.raises(DomainIssue, match='ENTRUST_UNKNOWN'):
        deliver(store, run_two['id'], 'WT-X')
    with pytest.raises(DomainIssue, match='ENTRUST_UNKNOWN'):
        withdraw(store, run_two['id'], 'WT-X')


# ---------- 授权撤销 ----------

def test_download_blocked_after_withdrawal(store, run_two):
    assert deliver(store, run_two['id'], 'WT-A')['entrust'] == 'WT-A'
    outcome = withdraw(store, run_two['id'], 'WT-A')
    assert outcome['revoked'] is True and outcome['updated']
    with pytest.raises(DomainIssue, match='AUTH_REVOKED'):
        deliver(store, run_two['id'], 'WT-A')
    # 撤销只针对本委托，另一委托不受影响
    assert deliver(store, run_two['id'], 'WT-B')['entrust'] == 'WT-B'


def test_withdrawal_is_idempotent(store, run_two):
    first = withdraw(store, run_two['id'], 'WT-A')
    second = withdraw(store, run_two['id'], 'WT-A')
    assert first['run_id'] == second['run_id']
    with pytest.raises(DomainIssue, match='AUTH_REVOKED'):
        deliver(store, run_two['id'], 'WT-A')


def test_revocation_posted_first_rejects_concurrent_download(store, run_two):
    """撤回先入账后，随后到达的下载必须被拒。"""
    withdraw(store, run_two['id'], 'WT-A')
    with pytest.raises(DomainIssue, match='AUTH_REVOKED'):
        deliver(store, run_two['id'], 'WT-A')


def test_concurrent_race_never_serves_download_after_revocation(store, run_two):
    """真正同时起跑：撤销一旦先提交，下载必失败；两种时序都不得违反规则。"""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    start = Barrier(2)

    def revoke_first():
        start.wait(5)
        withdraw(store, run_two['id'], 'WT-A')
        return 'REVOKED'

    def download_racing():
        start.wait(5)
        try:
            deliver(store, run_two['id'], 'WT-A')
            return 'DOWNLOADED'
        except DomainIssue as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda fn: fn(), [revoke_first, download_racing]))
    assert set(results) in ({'AUTH_REVOKED', 'REVOKED'}, {'DOWNLOADED', 'REVOKED'})
    # 无论竞争结果如何，竞争结束后的下载必须被拒
    with pytest.raises(DomainIssue, match='AUTH_REVOKED'):
        deliver(store, run_two['id'], 'WT-A')


def test_repeated_concurrent_attempts_never_serve_after_revocation(store, run_two):
    """撤销入账之后，并发下载一律拒绝，不存在漏网。"""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    run_id = run_two['id']
    withdraw(store, run_id, 'WT-A')
    start = Barrier(8)

    def attempt(_):
        start.wait(5)
        try:
            deliver(store, run_id, 'WT-A')
            return 'DOWNLOADED'
        except DomainIssue as error:
            return error.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert set(results) == {'AUTH_REVOKED'}


# ---------- 旧批缺原始测值：保留结论，标明无法复算，不拿新批补数 ----------

def _legacy_report():
    return {
        'manifest': {'run_id': 'legacy-run', 'created': '2026-01-01T00:00:00.000+00:00'},
        'cases': [{
            'case': 'OLD1', 'entrust': 'WT-A', 'records': [], 'sources': [],
            'status': 'READY', 'doubtful': {},
            'measure': {'evidence': {'pairs': {
                '1': {'mode': 'ABSOLUTE', 'value': 2, 'pass': True},
                '2': {'mode': 'RPD', 'value': 300, 'pass': False},
            }, 'failed': [2]}},
        }],
    }


def test_legacy_package_keeps_verdict_but_flags_cannot_recalculate():
    package = build_package(_legacy_report(), 'WT-A')
    assert {item['sample']: item['status'] for item in package['samples']} == {'1': 'PASS', '2': 'HELD'}
    assert all(item['recalculable'] is False for item in package['samples'])
    assert all(item['note'] == 'CANNOT_RECALCULATE' for item in package['samples'])
    assert all(item['readings'] == [] and item['method'] is None for item in package['samples'])
    # 当时结论原样保留
    verdicts = {item['sample']: item['verdict'] for item in package['samples']}
    assert verdicts['1'] == {'mode': 'ABSOLUTE', 'value': 2, 'pass': True}


def test_legacy_data_is_not_backfilled_from_new_batch(store, run_two):
    legacy = _legacy_report()
    store.register('legacy-run', legacy)
    package = deliver(store, 'legacy-run', 'WT-A')
    assert all(item['recalculable'] is False for item in package['samples'])
    assert all(item['readings'] == [] for item in package['samples'])
    # 旧批结论值保留，新批（run_two）的测值不得混入旧批交付件
    new_values = {100, 110, 8, 9, 50, 51}
    legacy_values = {2, 300}
    present = {value for item in package['samples'] for value in (item['verdict']['value'],)}
    assert present == legacy_values and present.isdisjoint(new_values)
    assert store.authorization_snapshot(run_two['id']) == {}
