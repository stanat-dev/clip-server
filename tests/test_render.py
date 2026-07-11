import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_create_render_returns_job_id(client):
    payload = {
        "trip_id": 1,
        "render_id": 10,
        "clip_keys": ["clips/1/a.mp4"],
        "bgm_key": "bgm/track.mp3",
        "template": "default",
        "watermark_text": "StanAt",
    }
    resp = await client.post("/internal/renders", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    assert "job_id" in body["data"]


@pytest.mark.asyncio
async def test_get_render_status(client):
    payload = {
        "trip_id": 2,
        "render_id": 20,
        "clip_keys": ["clips/2/b.mp4"],
        "bgm_key": "bgm/track.mp3",
        "template": "default",
        "watermark_text": "StanAt",
    }
    create_resp = await client.post("/internal/renders", json=payload)
    job_id = create_resp.json()["data"]["job_id"]

    status_resp = await client.get(f"/internal/renders/{job_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()["data"]
    assert data["job_id"] == job_id
    assert data["status"] in ("PENDING", "RUNNING", "DONE", "FAILED")


@pytest.mark.asyncio
async def test_get_render_not_found(client):
    resp = await client.get("/internal/renders/no-such-job")
    assert resp.status_code == 404
