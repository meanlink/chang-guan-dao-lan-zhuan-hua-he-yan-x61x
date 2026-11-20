import {datasets, holdouts} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {chart} from '../components/common/chart.js';
import {table} from '../components/common/table.js';
import {status} from '../components/common/status.js';
import {HoldoutBatchStatus, HoldoutTaskStatus} from '../constants/enums.js';
import {esc, fmt, date, notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';

const canWrite = () => session.user.role === 'admin' || session.user.role === 'analyst';
const isAdmin = () => session.user.role === 'admin';

function taskStateLabel(t) {
 return t ? HoldoutTaskStatus[t.status] || t.status : '尚未建立';
}
function batchStateLabel(s) {
 return HoldoutBatchStatus[s] || s;
}
function metricBlock(r) {
 if (!r?.metrics) return '';
 return '<div class="metrics">' + r.metrics.map(m => '<div><span>' + esc(m.label) + '</span><strong>' + esc(fmt(m.value)) + '<small>' + esc(m.unit || '') + '</small></strong></div>').join('') + '</div>';
}

function batchCard(b) {
 const t = b.task;
 const frozen = b.zone ? '<span>口径 ' + esc(b.zone) + ' · α=' + esc(b.alpha) + '</span>' : '<span>口径未登记</span>';
 const actions = [];
 if (b.status === 'sealed' && canWrite()) actions.push('<button class="button small" data-register="' + b.id + '">登记口径</button>');
 if (b.status === 'registered' && canWrite()) actions.push('<button class="primary small" data-unseal="' + b.id + '">受理开封</button>');
 if (b.status === 'unsealed' && t && t.status === 'failed' && canWrite()) actions.push('<button class="button small" data-retry="' + b.id + '">同任务续算</button>');
 if (b.status === 'unsealed' && isAdmin()) actions.push('<button class="text-button" data-records="' + b.id + '">读取明细</button>');
 const body = t && t.status === 'completed'
   ? '<section class="result-lead"><p class="eyebrow">CONFIRMATION RESULT</p><h2>' + esc(t.result.summary) + '</h2>' + metricBlock(t.result) + '</section>'
   : (t && t.status === 'failed' ? '<p class="warning">计算失败：' + esc(t.error || '未知错误') + '。参数保持固化，只能以同一任务续算，不得改参数。</p>'
   : '<p class="hint">状态：' + esc(taskStateLabel(t)) + (t ? ' · 已尝试 ' + t.attempts + ' 次' : '') + '</p>');
 return '<article class="holdout-card" data-batch="' + b.id + '"><div class="holdout-head"><div><strong>' + esc(b.name) + '</strong><p>来源批次 #' + b.dataset_id + ' · ' + b.rows + ' 条留样 · 比例 ' + Math.round(b.ratio * 100) + '% · 种子 ' + b.split_seed + '</p><small>SHA256 ' + esc(b.checksum.slice(0, 18)) + '… · 封存于 ' + date(b.created_at) + '</small></div><div class="holdout-badges"><span class="status ' + esc(b.status) + '">' + esc(batchStateLabel(b.status)) + '</span>' + (t ? '<span class="status ' + esc(t.status) + '">' + esc(taskStateLabel(t)) + '</span>' : '') + '</div></div><div class="holdout-meta">' + frozen + '<span>' + (b.unsealed_at ? '开封于 ' + date(b.unsealed_at) : '未开封') + '</span></div>' + body + '<div class="holdout-actions">' + actions.join('') + '</div><div class="records-slot"></div></article>';
}

function reviewCard(item) {
 const t = item.task, b = item.batch, r = t.result || {};
 return '<article class="panel review-card"><div class="section-title"><h2>' + esc(b.name) + '</h2><span>确认任务 #' + t.id + ' · ' + Math.round(b.ratio * 100) + '% 留样 · ' + esc(b.zone) + ' · α=' + esc(b.alpha) + '</span></div><p class="eyebrow">SEALED CONFIRMATION ONLY</p><h3>' + esc(r.summary || '') + '</h3>' + metricBlock(r) + chart(r.chart) + '<div class="section-title"><h2>逐项结果表</h2><span>' + (r.table?.rows?.length || 0) + ' 行</span></div>' + table(r.table?.columns || [], r.table?.rows || []) + (r.warnings || []).map(w => '<p class="warning">' + esc(w) + '</p>').join('') + '</article>';
}

export async function holdoutPage() {
 const [list, reviews, ds] = await Promise.all([holdouts.list(), holdouts.reviews(), datasets.list()]);
 workspace.datasets = ds;
 const m = workspace.meta;
 const sealable = canWrite();
 return heading('06 / HOLDOUT GOVERNANCE', '留样确认与封存治理', '同号记录不能同时进入探索批与确认批；封存明细不可读，登记展区与显著性门槛后开封，失败只允许同一任务续算。', '<button class="button" id="refresh-holdout">刷新工作台 ↻</button>')
 + '<div class="report-grid"><section class="panel"><div class="section-title"><h2>封存新确认批</h2><span>确定性切分 · 种子 1005</span></div>'
 + (sealable
   ? '<form id="holdout-form"><label>留样批次名称<input name="name" required minlength="2" value="' + esc(m.name) + ' · 确认批"></label><label>来源数据批次<select name="dataset_id" required>' + ds.map(d => '<option value="' + d.id + '">' + esc(d.name) + ' · ' + d.rows + ' 条</option>').join('') + '</select></label><div class="parameter-grid"><label>留样比例<select name="ratio"><option value="0.2">20%</option><option value="0.3" selected>30%</option><option value="0.4">40%</option><option value="0.5">50%</option></select></label><label>切分种子<input name="split_seed" type="number" min="1" value="1005" required></label></div><button type="submit" class="primary">封存确认批</button><p class="hint">封存后明细对所有角色不可读；同号记录会被全局锁定，探索分析拒绝再使用该批次。</p></form>'
   : '<p class="hint">观察员只有查看权限，不能封存或登记确认批。</p>')
 + '<div class="method-sheet compact" style="margin-top:25px"><p class="eyebrow">GOVERNANCE RULES</p><ul><li>同号记录探索批 / 确认批互斥，按 record 自然键切分。</li><li>封存期间越权读取明细一律拒绝，含业务负责人。</li><li>登记展区与显著性门槛后才能开封，参数即刻固化。</li><li>计算失败不得改参数，只能对同一确认任务续算。</li><li>并发开封以最先受理的登记为准，重试不新增任务。</li><li>留样评审只采纳已完成的确认结果。</li></ul></div></section>'
 + '<section><div class="section-title"><h2>确认批工作台</h2><span>' + list.length + ' 批 · 封存/待续算/结果</span></div><div class="holdout-list">' + (list.length ? list.map(batchCard).join('') : '<p class="empty">尚无封存批次。左侧创建第一批留样。</p>') + '</div>'
 + '<div class="section-title" style="margin-top:34px"><h2>留样评审</h2><span>仅完成的确认结果</span></div><div class="review-list">' + (reviews.length ? reviews.map(reviewCard).join('') : '<p class="empty">暂无完成的确认结果。运行中、失败或排队中的任务不会进入评审。</p>') + '</div></section></div>';
}

function renderRegisterDialog(id) {
 const m = workspace.meta;
 const zoneParam = m.parameters.find(p => p.key === 'zone');
 const alphaParam = m.parameters.find(p => p.key === 'alpha');
 return '<form id="register-form" data-batch="' + id + '"><input type="hidden" name="batch_id" value="' + id + '"><label>登记分析展区<select name="zone">' + zoneParam.options.map(o => '<option value="' + esc(o.value) + '">' + esc(o.label) + '</option>').join('') + '</select></label><label>登记显著性门槛<select name="alpha">' + alphaParam.options.map(o => '<option value="' + esc(o.value) + '">' + esc(o.label) + '</option>').join('') + '</select></label><button type="submit" class="primary small">确认登记（固化参数）</button><p class="hint">登记后不可修改；未登记不能开封。</p></form>';
}

export function bindHoldout(refresh) {
 document.querySelector('#refresh-holdout').onclick = refresh;
 const form = document.querySelector('#holdout-form');
 if (form) submit(form, async f => { await holdouts.seal({name: f.get('name'), dataset_id: Number(f.get('dataset_id')), ratio: Number(f.get('ratio')), split_seed: Number(f.get('split_seed'))}); notify('确认批已封存，明细已不可读'); await refresh(); });
 document.querySelectorAll('[data-register]').forEach(b => b.onclick = () => {
   const card = b.closest('.holdout-card');
   const slot = card.querySelector('.holdout-actions');
   slot.innerHTML = renderRegisterDialog(b.dataset.register);
   submit(slot.querySelector('#register-form'), async rf => {
     await holdouts.register(Number(rf.get('batch_id')), {zone: rf.get('zone'), alpha: Number(rf.get('alpha'))});
     notify('口径已登记固化，可受理开封'); await refresh();
   });
 });
 document.querySelectorAll('[data-unseal]').forEach(b => b.onclick = async () => {
   try { await holdouts.unseal(Number(b.dataset.unseal)); notify('已受理开封，确认任务已排队'); await refresh(); } catch (e) { notify(e.message, true); }
 });
 document.querySelectorAll('[data-retry]').forEach(b => b.onclick = async () => {
   try { await holdouts.retry(Number(b.dataset.retry)); notify('已按同一任务重新排队，未新增确认任务'); await refresh(); } catch (e) { notify(e.message, true); }
 });
 document.querySelectorAll('[data-records]').forEach(b => b.onclick = async () => {
   const card = b.closest('.holdout-card');
   const slot = card.querySelector('.records-slot');
   try {
     const detail = await holdouts.get(Number(b.dataset.records));
     slot.innerHTML = '<div class="section-title" style="margin-top:18px"><h2>确认批明细（仅负责人）</h2><span>' + detail.rows + ' 条</span></div>' + table(workspace.meta.columns, detail.records.slice(0, 50));
   } catch (e) { notify(e.message, true); }
 });
}
