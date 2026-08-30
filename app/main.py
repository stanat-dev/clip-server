from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.exceptions import ClipServerException, clip_server_exception_handler
from app.routers import render as render_router
from app.store.job_store import job_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 이전 프로세스가 비정상 종료(--reload 재시작 등)되며 PENDING/RUNNING 상태로 멈춘 job을 정리한다.
    orphaned = job_store.fail_orphaned_jobs()
    if orphaned:
        print(f"[startup] 고아 상태(PENDING/RUNNING) job {orphaned}건을 FAILED로 정리했습니다.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="StanAt Clip Server", lifespan=lifespan)
    app.add_exception_handler(ClipServerException, clip_server_exception_handler)
    app.include_router(render_router.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
