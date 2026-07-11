from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.exceptions import ClipServerException, clip_server_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="StanAt Clip Server", lifespan=lifespan)
    app.add_exception_handler(ClipServerException, clip_server_exception_handler)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
