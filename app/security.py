from fastapi import Header

from app.config import settings
from app.exceptions import ClipServerException

INTERNAL_SECRET_HEADER = "X-Internal-Secret"


async def verify_internal_secret(x_internal_secret: str | None = Header(default=None, alias=INTERNAL_SECRET_HEADER)) -> None:
    """Spring이 보낸 내부 시크릿 헤더를 검증한다. 이 서버는 Spring → Python 단방향 내부 전용 호출만 받는다."""
    if x_internal_secret != settings.internal_secret:
        raise ClipServerException(401, "UNAUTHORIZED", "Invalid or missing internal secret")
