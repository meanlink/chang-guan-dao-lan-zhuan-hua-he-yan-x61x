from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
class HoldoutStatus(str, Enum):
    # 封存：明细不可读；已登记：参数固化待开封；已开封：确认任务接管批次
    sealed = 'sealed'
    registered = 'registered'
    unsealed = 'unsealed'
class HoldoutTaskStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
