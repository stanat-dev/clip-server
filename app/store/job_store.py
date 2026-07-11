import threading

from app.schemas.common import JobStatus, JobStatusEnum


class JobStore:
    def __init__(self):
        self._store: dict[str, JobStatus] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str) -> JobStatus:
        job = JobStatus(job_id=job_id, status=JobStatusEnum.PENDING)
        with self._lock:
            self._store[job_id] = job
        return job

    def get(self, job_id: str) -> JobStatus | None:
        with self._lock:
            return self._store.get(job_id)

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            job = self._store.get(job_id)
            if job is None:
                return
            updated = job.model_copy(update=kwargs)
            self._store[job_id] = updated

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


job_store = JobStore()
