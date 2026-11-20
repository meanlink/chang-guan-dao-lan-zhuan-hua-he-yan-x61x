import time, json, logging
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Job, Dataset, Report, HoldoutTask
from src.services.business import analyze
from src.services.reports import deliver
from src.services import holdout
from src.services.audit import record
logging.basicConfig(level=logging.INFO)
def execute(job_id):
    with Session() as db:
        j=db.get(Job,job_id)
        if not j or j.status!='queued':return
        j.status='running'; db.commit()
        try:
            d=db.get(Dataset,j.dataset_id)
            result=analyze(d.records,j.params)
            json.dumps(result,allow_nan=False)
            j.result=result;j.status='completed';j.finished_at=time.time()
            record(db,'worker','job.completed',{'id':j.id})
        except Exception as e:
            logging.exception('Analysis failed')
            j.status='failed';j.error=str(e)[:990];j.finished_at=time.time()
            record(db,'worker','job.failed',{'id':j.id,'error':j.error})
        db.commit()
def execute_holdout(task_id):
    # 中断恢复与重试都复用同一任务，不新建确认任务
    with Session() as db:
        holdout.execute(db,task_id)
        t=db.get(HoldoutTask,task_id)
        if t:
            action='holdout.completed' if t.status=='completed' else 'holdout.failed'
            record(db,'worker',action,{'id':t.id,'attempts':t.attempts})
        db.commit()
def tick():
    with Session() as db:
        queued=list(db.scalars(select(Job.id).where(Job.status=='queued').limit(3)))
        holdout_queued=list(db.scalars(select(HoldoutTask.id).where(HoldoutTask.status=='queued').limit(3)))
    for job_id in queued:execute(job_id)
    for task_id in holdout_queued:execute_holdout(task_id)
    with Session() as db:
        for r in db.scalars(select(Report).where(Report.enabled==True,Report.next_run<=time.time())):
            d=deliver(db,r)
            if d:record(db,'worker','report.delivered',{'id':r.id,'delivery':d.id})
        db.commit()
def recover():
    # This Compose stack has a single worker. A crash must not strand its jobs.
    with Session() as db:
        for j in db.scalars(select(Job).where(Job.status=='running')):
            j.status='queued';record(db,'worker','job.recovered',{'id':j.id})
        # 确认任务同样按同一任务恢复：状态回到 queued，任务与固化参数保持不变
        for t in db.scalars(select(HoldoutTask).where(HoldoutTask.status=='running')):
            t.status='queued';record(db,'worker','holdout.recovered',{'id':t.id})
        db.commit()
def main():
    r=Redis.from_url(REDIS_URL,socket_timeout=3)
    recover()
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            item=r.blpop('analysis:queue',timeout=1)
            if item:execute(int(item[1]))
            item=r.blpop('holdout:queue',timeout=1)
            if item:execute_holdout(int(item[1]))
            tick()
        except Exception:
            logging.exception('Worker retry');time.sleep(2)
if __name__=='__main__':main()
