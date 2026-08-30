import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.security import INTERNAL_SECRET_HEADER
from app.store.job_store import job_store


@pytest.fixture(autouse=True)
def fake_job_store_redis():
    """단위 테스트는 실제 Redis 없이 통과해야 하므로(README §5) job_store의 Redis 클라이언트를
    fakeredis로 교체한다. FFmpeg/R2 mock과 동일한 취지."""
    original_client = job_store._client
    job_store._client = fakeredis.FakeRedis(decode_responses=True)
    yield
    job_store._client = original_client


@pytest.fixture
async def client():
    """Spring이 항상 내부 시크릿 헤더를 보내는 상황을 기본값으로 가정한다.
    헤더 누락/불일치 케이스는 개별 테스트에서 headers=...로 덮어써서 검증한다."""
    headers = {INTERNAL_SECRET_HEADER: settings.internal_secret}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as c:
        yield c
