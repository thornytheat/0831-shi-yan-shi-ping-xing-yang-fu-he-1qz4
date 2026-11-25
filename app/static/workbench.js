import {request, element} from './client.js';
import {snapshot, history, badge} from './view.js';
import {visualize} from './plots.js';

const form = document.querySelector('#source');
const file = document.querySelector('#file');
const profile = document.querySelector('#profile');
const status = document.querySelector('#notice');
const detail = document.querySelector('#review');
const evidence = document.querySelector('#evidence');
const stages = [...document.querySelectorAll('[data-stage]')];
let stage = 'balance';
let report, selected, batch, running = false;
const revoked = new Set();

function source() {
  const data = new FormData();
  if (file.files.length) data.append('file',file.files[0]);
  else data.append('sample',profile.value);
  return data;
}

function announce(text, failure = false) {
  status.textContent = text;
  status.dataset.failure = String(failure);
}

function draw() {
  if (!report) return;
  snapshot(report, selected, stage);
  visualize(report, selected);
  for (const button of stages) button.setAttribute('aria-pressed',String(button.dataset.stage===stage));
  document.querySelector('#panel-title').textContent = stages.find(button => button.dataset.stage===stage)?.textContent || '运行对账';
  detail.hidden = !batch;
  if (batch) {
    document.querySelector('#run-status').textContent = `${batch.id.slice(0,10)} · ${batch.status} · r${batch.revision}`;
    detail.querySelector('[value="APPROVED"]').disabled = !report.balance.releasable || batch.status==='APPROVED';
    detail.querySelector('[value="HELD"]').disabled = batch.status==='APPROVED';
    evidence.href = `/api/runs/${batch.id}/evidence`;
    renderDeliveries();
  }
}

function renderDeliveries() {
  const panel = document.querySelector('#delivery');
  const list = document.querySelector('#entrust-list');
  panel.hidden = !batch;
  list.replaceChildren();
  if (!batch) return;
  const revokedKey = entrust => `${batch.id}:${entrust}`;
  const doubtfulByEntrust = new Map();
  for (const caseRow of report.cases || []) {
    const count = Object.keys(caseRow.doubtful || {}).length;
    if (count) doubtfulByEntrust.set(caseRow.entrust, (doubtfulByEntrust.get(caseRow.entrust) || 0) + count);
  }
  for (const entrust of report.balance.entrusts || []) {
    const item = element('li');
    const name = element('span', entrust, {class:'entrust-name'});
    item.append(name);
    if (doubtfulByEntrust.has(entrust)) item.append(badge('DOUBTFUL'));
    const download = element('a', revoked.has(revokedKey(entrust)) ? '授权已撤回' : '下载交付件',
      {href: `/api/runs/${batch.id}/deliveries/${encodeURIComponent(entrust)}`});
    if (revoked.has(revokedKey(entrust))) {
      download.removeAttribute('href');
      download.classList.add('is-revoked');
      download.setAttribute('aria-disabled', 'true');
    }
    const revoke = element('button', '撤回授权',
      {type: 'button', class: 'revoke', 'data-entrust': entrust});
    if (revoked.has(revokedKey(entrust))) revoke.disabled = true;
    item.append(download, revoke);
    list.append(item);
  }
}

function show(payload, committed = false) {
  batch = committed ? payload : null;
  report = committed ? payload.report : payload;
  detail.elements.note.value = batch?.note || '';
  selected = report.cases?.[0]?.case;
  draw();
}

async function refresh() {
  const data = await request('/api/runs');
  history(data.items, batch?.id);
}

async function perform(action) {
  if (running) return;
  running = true;
  document.body.setAttribute('aria-busy','true');
  announce('处理中…');
  try { await action(); }
  catch (error) { announce(error.message,true); }
  finally { running = false; document.body.removeAttribute('aria-busy'); }
}

function preview(next) {
  return perform(async () => {
    const payload = await request(`/api/stages/${next}`,{method:'POST',body:source()});
    stage = next;
    show(payload);
    announce('阶段预览已更新');
    await refresh();
  });
}

stages.forEach(button => button.addEventListener('click',()=>preview(button.dataset.stage)));
form.addEventListener('submit', event => {
  event.preventDefault();
  perform(async () => {
    const result = await request('/api/runs',{method:'POST',body:source()});
    stage = 'balance'; show(result,true);
    announce('批次已保存'); await refresh();
  });
});
const filename = document.querySelector('#file-name');
profile.addEventListener('change',()=>{file.value=''; filename.textContent=''; preview(stage);});
file.addEventListener('change',()=>{filename.textContent=file.files[0]?.name || ''; preview(stage);});
document.querySelector('#rows').addEventListener('click',event=>{
  const button = event.target.closest('[data-case]');
  if (button) { selected = button.dataset.case; draw(); document.querySelector(`[data-case="${CSS.escape(selected)}"]`).focus(); }
});
document.querySelector('#history').addEventListener('click',event=>{
  const button = event.target.closest('[data-run]');
  if (button) perform(async()=>{
    const result = await request(`/api/runs/${button.dataset.run}`);
    stage='balance'; show(result,true); announce('已载入历史批次'); await refresh();
  });
});
detail.addEventListener('submit',event=>{
  event.preventDefault();
  perform(async()=>{
    const payload={status:event.submitter.value,revision:batch.revision,note:detail.elements.note.value};
    const result=await request(`/api/runs/${batch.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    show(result,true); announce(result.status==='APPROVED'?'批次已签发':'批次已暂缓'); await refresh();
  });
});
document.querySelector('#entrust-list').addEventListener('click',event=>{
  const button = event.target.closest('[data-entrust]');
  if (!button) return;
  const entrust = button.dataset.entrust;
  perform(async()=>{
    await request(`/api/runs/${batch.id}/deliveries/${encodeURIComponent(entrust)}/withdraw`,{method:'POST'});
    revoked.add(`${batch.id}:${entrust}`);
    renderDeliveries();
    announce(`委托 ${entrust} 的授权已撤回，后续下载将被拒绝`);
  });
});
preview(stage);
