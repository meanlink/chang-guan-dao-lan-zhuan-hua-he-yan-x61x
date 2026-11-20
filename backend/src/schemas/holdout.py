from pydantic import BaseModel, Field
class HoldoutSealInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    dataset_id: int
    ratio: float = Field(default=0.3, ge=0.1, le=0.5)
    split_seed: int = Field(default=1005, ge=1, le=9_999_999)
class HoldoutRegisterInput(BaseModel):
    zone: str = Field(min_length=1, max_length=40)
    alpha: float
