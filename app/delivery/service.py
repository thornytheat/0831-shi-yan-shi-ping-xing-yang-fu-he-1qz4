"""委托交付与授权撤销。

并发约定：撤销与下载同时到达时，谁先完成数据库事务谁先生效；
下载在读取授权台账后才生成交付件，因此一旦撤销先入账，本次下载必然被拒绝。
"""
from app.business import DomainIssue
from app.delivery.package import build_package, entrusts_of
from app.review.service import now


def deliver(store, run_id, entrust):
    run = store.load(run_id)
    if entrust not in entrusts_of(run['report']):
        raise DomainIssue('ENTRUST_UNKNOWN')
    if store.is_revoked(run_id, entrust):
        raise DomainIssue('AUTH_REVOKED')
    package = build_package(run['report'], entrust)
    if package is None:
        raise DomainIssue('ENTRUST_UNKNOWN')
    return package


def withdraw(store, run_id, entrust):
    run = store.load(run_id)
    if entrust not in entrusts_of(run['report']):
        raise DomainIssue('ENTRUST_UNKNOWN')
    updated = store.revoke(run_id, entrust, now())
    return {'run_id': run_id, 'entrust': entrust, 'revoked': True, 'updated': updated}
