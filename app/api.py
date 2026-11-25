import json

from flask import Blueprint, Response, current_app, jsonify, request

from app.business import DomainIssue
from app.delivery.service import deliver, withdraw
from app.evidence.render import artifact
from app.inputs import read_input
from app.modules.pipeline import run
from app.review.service import execute, review

api = Blueprint('api',__name__,url_prefix='/api')
STAGES = {'intake':1,'prepare':2,'calculate':3,'policy':4,'balance':5}


@api.post('/stages/<stage>')
def preview(stage):
    if stage not in STAGES:
        raise DomainIssue('STAGE_UNKNOWN')
    return jsonify(run(read_input(),STAGES[stage]))


@api.route('/runs',methods=['GET','POST'])
def runs():
    store = current_app.extensions['runs']
    if request.method == 'GET':
        return jsonify(items=store.list())
    return jsonify(execute(store,read_input()))


@api.route('/runs/<run_id>', methods=['GET','PATCH'])
def batch(run_id):
    store = current_app.extensions['runs']
    if request.method == 'GET':
        return jsonify(store.load(run_id))
    return jsonify(review(store,run_id,request.get_json(silent=True)))


@api.get('/runs/<run_id>/evidence')
def export(run_id):
    report = current_app.extensions['runs'].load(run_id)
    return Response(artifact(report),mimetype='application/json', headers={
        'Content-Disposition':f'attachment; filename="review-{report["id"][:12]}.json"',
        'Cache-Control':'no-store',
    })


@api.get('/runs/<run_id>/deliveries/<entrust>')
def delivery(run_id, entrust):
    store = current_app.extensions['runs']
    packet = deliver(store, run_id, entrust)
    body = (json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
    return Response(body, mimetype='application/json', headers={
        'Content-Disposition': f'attachment; filename="delivery-{entrust}-{run_id[:8]}.json"',
        'Cache-Control': 'no-store',
    })


@api.post('/runs/<run_id>/deliveries/<entrust>/withdraw')
def delivery_withdraw(run_id, entrust):
    return jsonify(withdraw(current_app.extensions['runs'], run_id, entrust))
