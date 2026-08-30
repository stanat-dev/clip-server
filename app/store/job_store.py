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

    def fail_orphaned_jobs(self, message: str = "서버 재시작으로 합성이 중단되었습니다. 다시 시도해주세요.") -> int:
        """PENDING/RUNNING 상태로 남아있는 job을 FAILED로 정리한다.

        Job 상태는 Redis에 남지만, 실제 처리는 그 프로세스의 이벤트 루프에 떠 있는
        asyncio 태스크(_run_render)다. 서버가 재시작(--reload 등)되면 그 태스크는
        그대로 사라지고, Redis에는 마지막 진행률이 영원히 고정된 채로 남는다 —
        폴링하는 Spring 쪽에서는 이게 "멈춘 건지 아직 처리 중인지" 구분할 수 없다.
        서버 기동 시 한 번 호출해 그런 고아 job을 명시적으로 FAILED 처리한다.

        반환값은 정리된 job 개수.
        """
        count = 0
        for key in self._client.scan_iter(f"{_KEY_PREFIX}*"):
            raw = self._client.get(key)
            if raw is None:
                continue
            job = JobStatus.model_validate_json(raw)
            if job.status in (JobStatusEnum.PENDING, JobStatusEnum.RUNNING):
                updated = job.model_copy(update={"status": JobStatusEnum.FAILED, "error": message})
                self._client.set(key, updated.model_dump_json(), ex=_JOB_TTL_SECONDS)
                count += 1
        return count


job_store = JobStore()
