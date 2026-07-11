import pytest

from app.store.job_store import job_store
from app.schemas.common import JobStatusEnum


def test_create_and_get():
    job_store.clear()
    job = job_store.create("job-1")
    assert job.job_id == "job-1"
    assert job.status == JobStatusEnum.PENDING
    assert job_store.get("job-1") is not None


def test_update_status():
    job_store.clear()
    job_store.create("job-2")
    job_store.update("job-2", status=JobStatusEnum.RUNNING, progress=50, step_message="동선 계산")
    updated = job_store.get("job-2")
    assert updated.status == JobStatusEnum.RUNNING
    assert updated.progress == 50
    assert updated.step_message == "동선 계산"


def test_get_missing_returns_none():
    job_store.clear()
    assert job_store.get("nonexistent") is None
