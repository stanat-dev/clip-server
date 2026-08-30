import redis

from app.config import settings
from app.schemas.common import JobStatus, JobStatusEnum

_KEY_PREFIX = "clip-server:job:"
_JOB_TTL_SECONDS = 3600  # 폴링이 끝날 때까지만 필요한 단명 상태이므로 1시간이면 충분하다


class JobStore:
    """Job 상태 저장소. Spring(user/infrastructure/redis)과 같은 Redis 인스턴스를 공유하되,
    키 프리픽스로 네임스페이스를 분리한다. 프로세스 재시작/다중 인스턴스에도 상태가 유지된다."""

    def __init__(self, client: redis.Redis | None = None):
        self._client = client or redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            decode_responses=True,
        )

    def _key(self, job_id: str) -> str:
        return f"{_KEY_PREFIX}{job_id}"

    def create(self, job_id: str) -> JobStatus:
        job = JobStatus(job_id=job_id, status=JobStatusEnum.PENDING)
        self._client.set(self._key(job_id), job.model_dump_json(), ex=_JOB_TTL_SECONDS)
        return job

    def get(self, job_id: str) -> JobStatus | None:
        raw = self._client.get(self._key(job_id))
        if raw is None:
            return None
        return JobStatus.model_validate_json(raw)

    def update(self, job_id: str, **kwargs) -> None:
        job = self.get(job_id)
        if job is None:
            return
        updated = job.model_copy(update=kwargs)
        self._client.set(self._key(job_id), updated.model_dump_json(), ex=_JOB_TTL_SECONDS)

    def clear(self) -> None:
        for key in self._client.scan_iter(f"{_KEY_PREFIX}*"):
            self._client.delete(key)


job_store = JobStore()
