import asyncio
import os
import tempfile
import uuid

import ffmpeg

from app.schemas.common import JobStatusEnum
from app.schemas.render import RenderRequest
from app.storage.r2_client import make_r2_client
from app.store.job_store import job_store


def _validate_clip_duration(path: str) -> None:
    """클립 길이가 5초 이내인지 검증한다."""
    probe = ffmpeg.probe(path)
    duration = float(probe["format"]["duration"])
    if duration > 5.0:
        raise ValueError(f"클립 길이 {duration:.1f}s — 5초 이내여야 함")


def _normalize_clip(src_path: str, out_path: str) -> None:
    """클립을 촬영한 클라이언트(모바일 웹, 네이티브 앱 등)에 관계없이 동일한
    해상도/fps/코덱/픽셀 포맷으로 재인코딩한다.

    모바일 웹(Android Chrome은 webm/VP9+Opus, iOS Safari는 mp4/H.264 계열)과
    네이티브 앱(mp4/mov, H.264/HEVC)이 서로 다른 컨테이너·코덱을 만들어내므로,
    이 정규화 단계 없이 바로 concat하면 클립 조합에 따라 실패하거나 결과가
    깨질 수 있다. 정규화는 파일의 실제 코덱/해상도만 보고 처리하므로 클라이언트
    종류를 나타내는 값을 요청에 별도로 실어 보낼 필요가 없다.
    """
    (
        ffmpeg
        .input(src_path)
        .output(
            out_path,
            vf=(
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
            ),
            r=30,
            vcodec="libx264",
            pix_fmt="yuv420p",
            acodec="aac",
            ar=48000,
            ac=2,
        )
        .run(overwrite_output=True, quiet=True)
    )


def _composite_clips(clip_paths: list[str], bgm_path: str | None, watermark: str, out_path: str) -> None:
    """FFmpeg로 (정규화된) 클립 concat → BGM 오버레이 → 워터마크 텍스트 번인.

    입력 clip_paths는 이미 `_normalize_clip`을 거친 동일 스펙 파일이어야 한다.
    """
    if not clip_paths:
        raise ValueError("clip_paths must not be empty")

    inputs = [ffmpeg.input(p) for p in clip_paths]

    # 클립을 순서대로 이어 붙이기
    concat = ffmpeg.concat(*inputs, v=1, a=0).node
    video = concat[0]

    # 워터마크 텍스트
    video = ffmpeg.drawtext(
        video,
        text=watermark,
        fontsize=24,
        fontcolor="white",
        x="(w-text_w)/2",
        y="h-40",
    )

    # BGM 믹싱
    if bgm_path:
        audio_input = ffmpeg.input(bgm_path)
        out = ffmpeg.output(video, audio_input.audio, out_path, shortest=None)
    else:
        out = ffmpeg.output(video, out_path)

    ffmpeg.run(out, overwrite_output=True, quiet=True)


async def _run_render(job_id: str, req: RenderRequest) -> None:
    r2 = make_r2_client()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            job_store.update(job_id, status=JobStatusEnum.RUNNING, progress=10, step_message="클립 다운로드·정규화")

            clip_paths: list[str] = []
            for i, key in enumerate(req.clip_keys):
                src = os.path.join(tmpdir, f"clip_src_{i}.mp4")
                await asyncio.to_thread(r2.download, key, src)
                await asyncio.to_thread(_validate_clip_duration, src)

                normalized = os.path.join(tmpdir, f"clip_norm_{i}.mp4")
                await asyncio.to_thread(_normalize_clip, src, normalized)
                clip_paths.append(normalized)

            bgm_path: str | None = None
            if req.bgm_key:
                bgm_path = os.path.join(tmpdir, "bgm.mp3")
                await asyncio.to_thread(r2.download, req.bgm_key, bgm_path)

            job_store.update(job_id, progress=50, step_message="영상 합성")
            out_path = os.path.join(tmpdir, "output.mp4")
            await asyncio.to_thread(
                _composite_clips, clip_paths, bgm_path, req.watermark_text, out_path
            )

            job_store.update(job_id, progress=80, step_message="업로드")
            result_key = f"renders/{req.trip_id}/{req.render_id}.mp4"
            await asyncio.to_thread(r2.upload, out_path, result_key, "video/mp4")

            job_store.update(
                job_id,
                status=JobStatusEnum.DONE,
                progress=100,
                step_message="완료",
                result_key=result_key,
            )
    except Exception as exc:
        job_store.update(job_id, status=JobStatusEnum.FAILED, error=str(exc))


def start_render(req: RenderRequest) -> str:
    job_id = str(uuid.uuid4())
    job_store.create(job_id)
    asyncio.ensure_future(_run_render(job_id, req))
    return job_id
