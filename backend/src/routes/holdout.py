from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import HoldoutBatch, HoldoutTask
from src.schemas.holdout import HoldoutSealInput, HoldoutRegisterInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import holdout
from src.services.audit import record
from src.utils.serialization import holdout_batch_dict, holdout_task_dict
router = APIRouter(prefix='/holdouts')


@router.get('')
def listing(db=Depends(get_db), u=Depends(current_user)):
    # 工作台：查看封存、待续算和确认结果；列表不含明细
    rows = []
    for b in db.scalars(select(HoldoutBatch).order_by(HoldoutBatch.id.desc())):
        item = holdout_batch_dict(b)
        task = db.scalar(select(HoldoutTask).where(HoldoutTask.batch_id == b.id))
        item['task'] = holdout_task_dict(task) if task else None
        rows.append(item)
    return rows


@router.post('', status_code=201)
def seal(data: HoldoutSealInput, db=Depends(get_db), u=Depends(can_write)):
    b = holdout.seal(db, data, u)
    record(db, u.email, 'holdout.seal', {'id': b.id, 'dataset_id': b.dataset_id, 'rows': len(b.records)})
    db.commit()
    return holdout_batch_dict(b)


@router.get('/reviews/completed')
def reviews(db=Depends(get_db), u=Depends(current_user)):
    # 留样评审只认完成的确认结果：failed/running/queued 不进入评审
    stmt = (select(HoldoutTask, HoldoutBatch)
            .join(HoldoutBatch, HoldoutTask.batch_id == HoldoutBatch.id)
            .where(HoldoutTask.status == 'completed')
            .order_by(HoldoutTask.id.desc()))
    return [{'task': holdout_task_dict(t), 'batch': holdout_batch_dict(b)} for t, b in db.execute(stmt)]


@router.get('/{id}')
def detail(id: int, db=Depends(get_db), u=Depends(current_user)):
    b = db.get(HoldoutBatch, id)
    if not b:
        raise HTTPException(404, '留样批次不存在')
    # 封存阶段：越权读取明细一律拒绝，admin 也不例外
    if b.status == 'sealed':
        raise HTTPException(403, '确认批封存中，登记展区与显著性门槛并开封后方可读取明细')
    if u.role != 'admin':
        raise HTTPException(403, '确认批明细仅业务负责人可读取，分析员与观察员可查看确认结果')
    return holdout_batch_dict(b, include_records=True)


@router.post('/{id}/register')
def register(id: int, data: HoldoutRegisterInput, db=Depends(get_db), u=Depends(can_write)):
    b = db.get(HoldoutBatch, id)
    if not b:
        raise HTTPException(404, '留样批次不存在')
    holdout.register(db, b, data, u)
    record(db, u.email, 'holdout.register', {'id': id, 'zone': b.zone, 'alpha': b.alpha})
    db.commit()
    return holdout_batch_dict(b)


@router.post('/{id}/unseal', status_code=201)
def unseal(id: int, db=Depends(get_db), u=Depends(can_write)):
    b, task = holdout.unseal(db, id, u)
    record(db, u.email, 'holdout.unseal', {'id': id, 'task': task.id})
    db.commit()
    holdout.enqueue(task.id)
    refreshed = db.get(HoldoutBatch, id)
    return {'batch': holdout_batch_dict(refreshed), 'task': holdout_task_dict(task)}


@router.post('/{id}/retry')
def retry(id: int, db=Depends(get_db), u=Depends(can_write)):
    b = db.get(HoldoutBatch, id)
    if not b:
        raise HTTPException(404, '留样批次不存在')
    task = holdout.retry(db, b, u)
    record(db, u.email, 'holdout.retry', {'id': id, 'task': task.id, 'attempts': task.attempts})
    db.commit()
    holdout.enqueue(task.id)
    return holdout_task_dict(task)


@router.get('/{id}/task')
def task(id: int, db=Depends(get_db), u=Depends(current_user)):
    b = db.get(HoldoutBatch, id)
    if not b:
        raise HTTPException(404, '留样批次不存在')
    task = db.scalar(select(HoldoutTask).where(HoldoutTask.batch_id == b.id))
    if not task:
        raise HTTPException(404, '确认任务尚未建立，需先登记并开封')
    return holdout_task_dict(task)
