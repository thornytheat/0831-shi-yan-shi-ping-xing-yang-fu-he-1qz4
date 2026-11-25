"""委托交付件的 HTTP 入口与状态码。"""


def _run_id(client, sample='dirty'):
    return client.post('/api/runs', data={'sample': sample}).json['id']


def test_delivery_attachment_is_scoped_to_entrust(client):
    run_id = _run_id(client)
    response = client.get(f'/api/runs/{run_id}/deliveries/WT-A')
    assert response.status_code == 200
    assert 'attachment' in response.headers['Content-Disposition']
    assert response.headers['Cache-Control'] == 'no-store'
    packet = response.json
    assert packet['schema'] == 'entrust-delivery/1' and packet['entrust'] == 'WT-A'
    blob = response.get_data(as_text=True)
    assert 'WT-B' not in blob and 'releasable' not in blob


def test_delivery_unknown_run_and_entrust_are_404(client):
    run_id = _run_id(client)
    assert client.get(f'/api/runs/{run_id}/deliveries/WT-X').status_code == 404
    assert client.get('/api/runs/missing/deliveries/WT-A').status_code == 404
    response = client.post(f'/api/runs/{run_id}/deliveries/WT-X/withdraw')
    assert response.status_code == 404 and response.json['code'] == 'ENTRUST_UNKNOWN'


def test_withdraw_then_download_returns_403(client):
    run_id = _run_id(client)
    withdrawn = client.post(f'/api/runs/{run_id}/deliveries/WT-A/withdraw')
    assert withdrawn.status_code == 200 and withdrawn.json['revoked'] is True
    blocked = client.get(f'/api/runs/{run_id}/deliveries/WT-A')
    assert blocked.status_code == 403 and blocked.json['code'] == 'AUTH_REVOKED'
    # 另一委托仍可下载
    assert client.get(f'/api/runs/{run_id}/deliveries/WT-B').status_code == 200


def test_withdraw_is_idempotent_over_http(client):
    run_id = _run_id(client)
    url = f'/api/runs/{run_id}/deliveries/WT-A/withdraw'
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 200
    assert client.get(f'/api/runs/{run_id}/deliveries/WT-A').status_code == 403


def test_delivery_works_for_uploaded_multi_entrust_file(client):
    run_id = _run_id(client, 'clean')
    response = client.get(f'/api/runs/{run_id}/deliveries/WT-A')
    assert response.status_code == 200
    assert response.json['totals']['samples'] == 3 and response.json['totals']['doubtful'] == 0


def test_full_batch_evidence_endpoint_remains_internal(client):
    run_id = _run_id(client)
    packet = client.get(f'/api/runs/{run_id}/deliveries/WT-A').json
    # 交付件只含委托自身的样品总数，不含整批统计
    assert set(packet) >= {'schema', 'entrust', 'samples', 'totals', 'scope'}
    assert all(key not in packet for key in ('balance', 'intake', 'cases'))
