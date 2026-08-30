from fastapi import APIRouter, Depends

from app.exceptions import ClipServerException
from app.schemas.common import ApiResponse, JobStatus
from app.schemas.render import RenderRequest, RenderResponse
from app.security import verify_internal_secret
from app.services.render_service import start_render
from app.store.job_store import job_store

router = APIRouter(prefix="/internal/renders", tags=["render"], dependencies=[Depends(verify_internal_secret)])


@router.post("", status_code=202)
async def create_render(req: RenderRequest) -> ApiResponse[RenderResponse]:
    job_id = start_render(req)
    return ApiResponse(data=RenderResponse(job_id=job_id))


@router.get("/{job_id}")
async def get_render_status(job_id: str) -> ApiResponse[JobStatus]:
    status = job_store.get(job_id)
    if status is None:
        raise ClipServerException(404, "JOB_NOT_FOUND", f"Job {job_id} not found")
    return ApiResponse(data=status)
