from pydantic import BaseModel


class ClipInput(BaseModel):
    key: str
    location_text: str
    captured_at: str


class RenderRequest(BaseModel):
    trip_id: int
    render_id: int
    clips: list[ClipInput]
    bgm_key: str | None = None
    template: str = "default"


class RenderResponse(BaseModel):
    job_id: str
