"""留样确认（holdout）治理：封存、登记、开封与同一任务续算。

业务红线：
- 同号记录不能同时进入探索批与确认批，按 record 自然键在封存时确定性切分；
- 封存明细任何角色都不能经接口读取，开封后明细仍仅 admin 可读；
- 登记展区与显著性门槛后参数即固化，开封与重试都不允许改参数；
- 每个确认批次至多一个确认任务，中断恢复/重试复用同一任务，不新增任务。
"""
import hashlib
import json
import random
import time
from fastapi import HTTPException
from sqlalchemy import select
from src.models import Dataset, HoldoutBatch, HoldoutTask
from src.services.business import metadata
from src.utils.serialization import checksum

ZONES = ('全部', '星空厅', '水世界', '机械坊')
ALPHAS = (0.01, 0.05, 0.1)


def sealed_keys(db, dataset_id=None):
    """全局已封存（含已登记/已开封）留样记录键，探索批一律不得再用。"""
    stmt = select(HoldoutBatch.record_keys)
    if dataset_id is not None:
        stmt = stmt.where(HoldoutBatch.dataset_id == dataset_id)
    keys = set()
    for chunk in db.scalars(stmt):
        keys.update(chunk)
    return keys


def _validate_zone_alpha(zone, alpha):
    if zone not in ZONES:
        raise HTTPException(422, '分析展区不是有效选项')
    try:
        alpha = float(alpha)
    except (TypeError, ValueError):
        raise HTTPException(422, '显著性水平必须为 0.01/0.05/0.1')
    if alpha not in ALPHAS:
        raise HTTPException(422, '显著性水平必须为 0.01/0.05/0.1')
    return zone, alpha


def _split_records(records, ratio, seed):
    """确定性、可复现的分层切分：按展区+方案分层后哈希排序，尾部为留样。"""
    layers = {}
    for row in records:
        layers.setdefault((str(row.get('zone')), str(row.get('arm'))), []).append(row)
    holdout = []
    for key in sorted(layers):
        rows = sorted(layers[key], key=lambda r: str(r.get('record')))
        rng = random.Random(seed + len(key[0]) * 31 + len(key[1]))
        rng.shuffle(rows)
        take = max(1, round(len(rows) * ratio))
        holdout.extend(rows[-take:])
    holdout.sort(key=lambda r: str(r.get('record')))
    return holdout


def seal(db, data, user):
    name = data.name.strip()
    if len(name) < 2:
        raise HTTPException(422, '留样批次名称去除空格后至少需要两个字符')
    if db.scalar(select(HoldoutBatch).where(HoldoutBatch.name == name)):
        raise HTTPException(409, '该留样批次名已存在，请修改名称')
    dataset = db.get(Dataset, data.dataset_id)
    if not dataset:
        raise HTTPException(404, '数据批次不存在')
    if db.scalar(select(HoldoutBatch).where(HoldoutBatch.dataset_id == dataset.id)):
        raise HTTPException(409, '该数据批次已封存过留样，确认批只能建立一次')
    records = dataset.records
    holdout = _split_records(records, data.ratio, data.split_seed)
    keys = [str(r['record']) for r in holdout]
    if len(keys) != len(set(keys)):
        raise HTTPException(422, '数据批次内存在同号记录，无法保证留样互斥')
    # 全局互斥：同一自然键不得在任何确认批中重复留样
    overlap = sealed_keys(db) & set(keys)
    if overlap:
        raise HTTPException(409, '同号记录已在其他确认批封存：' + '、'.join(sorted(overlap)[:5]))
    batch = HoldoutBatch(
        name=name, dataset_id=dataset.id, records=holdout, record_keys=keys,
        split_seed=data.split_seed, ratio=data.ratio, checksum=checksum(holdout),
        status='sealed', created_by=user.id, created_at=time.time(),
    )
    db.add(batch)
    db.flush()
    return batch


def register(db, batch, data, user):
    if batch.status != 'sealed':
        raise HTTPException(409, '该批次已登记确认口径，参数不允许修改')
    zone, alpha = _validate_zone_alpha(data.zone, data.alpha)
    batch.zone, batch.alpha = zone, alpha
    batch.status = 'registered'
    batch.registered_by = user.id
    batch.registered_at = time.time()
    db.flush()
    return batch


def unseal(db, batch_id, user):
    """行级锁串行化并发开封：最先受理的登记生效，其余请求拒绝。"""
    b = db.get(HoldoutBatch, batch_id, with_for_update=True)
    if not b:
        raise HTTPException(404, '留样批次不存在')
    if b.status == 'unsealed':
        raise HTTPException(409, '确认批次已开封，请勿重复受理')
    if b.status != 'registered':
        raise HTTPException(409, '封存留样须先登记展区与显著性门槛后才能开封')
    existing = db.scalar(select(HoldoutTask).where(HoldoutTask.batch_id == b.id))
    if existing:
        raise HTTPException(409, '确认任务已存在，不允许重复创建')
    params = {'zone': b.zone, 'alpha': b.alpha}
    task = HoldoutTask(
        batch_id=b.id, params=params, status='queued', attempts=0,
        created_by=user.id, created_at=time.time(),
    )
    b.status = 'unsealed'
    b.unsealed_at = time.time()
    db.add(task)
    db.flush()
    return b, task


def retry(db, batch, user):
    """失败后续算同一任务：参数不变、任务 ID 不变，仅重新排队。"""
    if batch.status != 'unsealed':
        raise HTTPException(409, '仅已开封批次可以续算')
    task = db.scalar(select(HoldoutTask).where(HoldoutTask.batch_id == batch.id))
    if not task:
        raise HTTPException(404, '确认任务不存在')
    if task.status == 'completed':
        raise HTTPException(409, '确认已完成，无需续算')
    if task.status in ('queued', 'running'):
        raise HTTPException(409, '确认任务已在队列中，请勿重复提交')
    task.status = 'queued'
    task.error = ''
    db.flush()
    return task


def enqueue(task_id):
    from redis import Redis
    from src.config.settings import REDIS_URL
    try:
        r = Redis.from_url(REDIS_URL)
        r.rpush('holdout:queue', task_id)
        r.close()
    except Exception:
        pass  # SQL queued 状态是持久兜底，worker tick 会捞起


def execute(db, task_id):
    """worker 调用：调用方负责事务提交；只处理 queued 任务，保证不新增任务。"""
    from src.services.business import analyze
    task = db.get(HoldoutTask, task_id)
    if not task or task.status != 'queued':
        return
    batch = db.get(HoldoutBatch, task.batch_id)
    task.status = 'running'
    task.attempts += 1
    db.commit()
    try:
        result = analyze(batch.records, task.params)
        json.dumps(result, allow_nan=False)
        task.result = result
        task.status = 'completed'
        task.error = ''
        task.finished_at = time.time()
    except Exception as e:
        # 算失败也不改参数：保留固化口径，只记录错误，等待同一任务重试
        task.status = 'failed'
        task.error = str(e)[:990]
        task.finished_at = time.time()


def batch_fingerprint(batch):
    return hashlib.sha256(
        (batch.checksum + '|' + str(batch.split_seed) + '|' + f'{batch.ratio:.4f}').encode()
    ).hexdigest()
