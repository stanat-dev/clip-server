import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_create_render_returns_job_id(client):
    payload = {
        "trip_id": 1,
        "user_id": 100,
        "render_id": 10,
        "clips": [
            {
                "key": "clips/1/a.mp4",
                "location_text": "해운대",
                "captured_at": "2026-07-10T14:32:00+09:00",
            }
        ],
        "bgm_key": "bgm/track.mp3",
        "template": "default",
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
        "user_id": 200,
        "render_id": 20,
        "clips": [
            {
                "key": "clips/2/b.mp4",
                "location_text": "광안리",
                "captured_at": "2026-07-10T16:05:00+09:00",
            }
        ],
        "bgm_key": "bgm/track.mp3",
        "template": "default",
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


@pytest.mark.asyncio
async def test_create_render_without_internal_secret_rejected(client):
    resp = await client.post(
        "/internal/renders",
        json={"trip_id": 1, "user_id": 1, "render_id": 1, "clips": []},
        headers={"X-Internal-Secret": ""},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_render_with_wrong_internal_secret_rejected(client):
    resp = await client.post(
        "/internal/renders",
        json={"trip_id": 1, "user_id": 1, "render_id": 1, "clips": []},
        headers={"X-Internal-Secret": "wrong-secret"},
    )
    assert resp.status_code == 401
