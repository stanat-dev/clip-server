from pydantic import BaseModel


class RenderRequest(BaseModel):
    trip_id: int
    render_id: int
    clip_keys: list[str]
    bgm_key: str | None = None
    template: str = "default"
    watermark_text: str = "StanAt"


class RenderResponse(BaseModel):
    job_id: str
