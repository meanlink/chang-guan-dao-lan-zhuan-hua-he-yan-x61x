import time
from fastapi import HTTPException
from redis import Redis
from src.config.settings import REDIS_URL
from src.models import Dataset, Job
from src.services.business import metadata
from src.services.holdout import sealed_keys
def create(db, data, user):
    if not db.get(Dataset,data.dataset_id): raise HTTPException(404,'数据批次不存在')
    dataset=db.get(Dataset,data.dataset_id)
    # 同号记录不能同时入探索批和确认批：含留样键的数据批次禁止再做探索分析
    blocked=sealed_keys(db,dataset.id)
    if blocked:
        leaked=[str(r.get('record')) for r in dataset.records if str(r.get('record')) in blocked][:5]
        if leaked:raise HTTPException(409,'该批次含已封存确认批同号记录，探索分析拒绝使用：'+'、'.join(leaked))
    allowed={p['key']:p for p in metadata().get('parameters',[])}
    if set(data.params)-set(allowed): raise HTTPException(422,'包含未知分析参数')
    params={k:p['default'] for k,p in allowed.items()}
    params.update(data.params)
    for key,p in allowed.items():
        v=params[key]
        if p['type']=='number':
            try:
                v=float(v)
                if not (p.get('min',-1e9)<=v<=p.get('max',1e9)): raise ValueError()
                params[key]=v
            except (ValueError,TypeError): raise HTTPException(422, f'{p["label"]} 超出范围或非数值')
        elif str(v) not in [str(o['value']) for o in p.get('options',[])]:
            raise HTTPException(422,f'{p["label"]} 不是有效选项')
    j=Job(name=data.name, dataset_id=data.dataset_id, params=params, created_by=user.id, created_at=time.time(), status='queued')
    db.add(j); db.flush()
    return j
def enqueue(job_id):
    try:
        r=Redis.from_url(REDIS_URL); r.rpush('analysis:queue',job_id); r.close()
    except Exception:
        pass # SQL queued status is the durable fallback
