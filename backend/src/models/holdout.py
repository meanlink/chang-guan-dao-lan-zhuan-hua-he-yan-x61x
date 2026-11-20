from sqlalchemy import String, JSON, Double, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class HoldoutBatch(Base):
    __tablename__ = 'holdout_batches'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    # sealed 阶段明细即已入库，但任何角色都不能经接口读取，开封后仍仅 admin 可取明细
    records: Mapped[list] = mapped_column(JSON)
    record_keys: Mapped[list] = mapped_column(JSON)
    split_seed: Mapped[int] = mapped_column(Integer, default=1005)
    ratio: Mapped[float] = mapped_column(Double)
    checksum: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default='sealed')
    # 登记后固化的确认口径；封存阶段为空
    zone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    alpha: Mapped[float | None] = mapped_column(Double, nullable=True)
    registered_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    registered_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    unsealed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
class HoldoutTask(Base):
    __tablename__ = 'holdout_tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    # 每个确认批次至多一个确认任务：中断恢复与重试都复用该任务，不新增任务
    batch_id: Mapped[int] = mapped_column(ForeignKey('holdout_batches.id'), unique=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(String(1000), default='')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    finished_at: Mapped[float | None] = mapped_column(Double, nullable=True)
