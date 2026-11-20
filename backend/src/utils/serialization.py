import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def holdout_batch_dict(b, include_records=False):
    # 封存阶段对任何角色都不返回明细；开封后仅路由层在 admin 请求时显式带 records
    data={'id':b.id,'name':b.name,'dataset_id':b.dataset_id,'status':b.status,
          'rows':len(b.records),'record_keys':list(b.record_keys),
          'split_seed':b.split_seed,'ratio':b.ratio,'checksum':b.checksum,
          'zone':b.zone,'alpha':b.alpha,'registered_at':b.registered_at,
          'unsealed_at':b.unsealed_at,'created_by':b.created_by,'created_at':b.created_at}
    if include_records:data['records']=b.records
    return data
def holdout_task_dict(t):
    return {k:getattr(t,k) for k in ['id','batch_id','params','status','result','error','attempts','created_at','finished_at']}
