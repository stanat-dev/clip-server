from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None


class JobStatusEnum(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class JobStatus(BaseModel):
    job_id: str
    status: JobStatusEnum
    progress: int = 0          # 0~100
    step_message: str = ""
    result_key: str | None = None  # R2 오브젝트 키 (DONE 시 채워짐). presigned URL 생성은 Spring 담당
    error: str | None = None
