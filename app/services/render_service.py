import asyncio
import os
import tempfile
import uuid
from datetime import datetime

import ffmpeg

from app.schemas.common import JobStatusEnum
from app.schemas.render import RenderRequest
from app.storage.r2_client import make_r2_client
from app.store.job_store import job_store

NOTO_SANS_KR_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"


def _format_watermark_date(captured_at: str) -> str:
    dt = datetime.fromisoformat(captured_at)
    return f"{dt.month}/{dt.day} {dt.hour:02d}:{dt.minute:02d}"


def _validate_clip_duration(path: str) -> None:
    """클립 길이가 5초 이내인지 검증한다."""
    probe = ffmpeg.probe(path)
    duration = float(probe["format"]["duration"])
    if duration > 5.0:
        raise ValueError(f"클립 길이 {duration:.1f}s — 5초 이내여야 함")


def _normalize_and_watermark_clip(
    src_path: str, location_text: str, captured_at: str, out_path: str
) -> None:
    """클립을 4:3(1440x1080) 가로로 정규화하고 우측 하단에 장소명+촬영시각을 번인한다.

    클립을 촬영한 클라이언트(모바일 웹, 네이티브 앱 등)에 관계없이 동일한
    해상도/fps/코덱/픽셀 포맷으로 재인코딩하는 정규화 책임과, 클립별로 다른
    워터마크(장소명/시각) 번인 책임을 하나의 ffmpeg 호출로 합쳐 재인코딩을
    1회로 유지한다. concat 단계(`_composite_clips`)는 이미 번인이 끝난
    클립들을 이어붙이기만 한다.
    """
    date_str = _format_watermark_date(captured_at)

    stream = ffmpeg.input(src_path)
    video = (
        stream.video
        .filter("scale", 1440, 1080, force_original_aspect_ratio="decrease")
        .filter("pad", 1440, 1080, "(ow-iw)/2", "(oh-ih)/2")
        .filter("setsar", 1)
    )
    video = ffmpeg.drawtext(
        video,
        text=date_str,
        fontfile=NOTO_SANS_KR_PATH,
        fontsize=22,
        fontcolor="white",
        borderw=2,
        bordercolor="black",
        x="w-text_w-24",
        y="h-70",
    )
    video = ffmpeg.drawtext(
        video,
        text=location_text,
        fontfile=NOTO_SANS_KR_PATH,
        fontsize=36,
        fontcolor="white",
        borderw=2,
        bordercolor="black",
        x="w-text_w-24",
        y="h-40",
    )

    (
        ffmpeg
        .output(
            video,
            stream.audio,
            out_path,
            r=30,
            vcodec="libx264",
            crf=26,
            maxrate="4M",
            bufsize="8M",
            pix_fmt="yuv420p",
            acodec="aac",
            ar=48000,
            ac=2,
        )
        .run(overwrite_output=True, quiet=True)
    )


def _composite_clips(clip_paths: list[str], bgm_path: str | None, out_path: str) -> None:
    """FFmpeg로 (정규화+워터마크 번인된) 클립 concat → BGM 오버레이.

    입력 clip_paths는 이미 `_normalize_and_watermark_clip`을 거친 동일 스펙
    파일이어야 한다. 이 함수는 워터마크 책임을 갖지 않는다.
    """
    if not clip_paths:
        raise ValueError("clip_paths must not be empty")

    inputs = [ffmpeg.input(p) for p in clip_paths]

    concat = ffmpeg.concat(*inputs, v=1, a=0).node
    video = concat[0]

    if bgm_path:
        audio_input = ffmpeg.input(bgm_path)
        out = ffmpeg.output(
            video,
            audio_input.audio,
            out_path,
            shortest=None,
            vcodec="libx264",
            crf=26,
            maxrate="4M",
            bufsize="8M",
            pix_fmt="yuv420p",
            acodec="aac",
        )
    else:
        out = ffmpeg.output(
            video,
            out_path,
            vcodec="libx264",
            crf=26,
            maxrate="4M",
            bufsize="8M",
            pix_fmt="yuv420p",
        )

    ffmpeg.run(out, overwrite_output=True, quiet=True)


async def _run_render(job_id: str, req: RenderRequest) -> None:
    r2 = make_r2_client()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            job_store.update(job_id, status=JobStatusEnum.RUNNING, progress=10, step_message="클립 다운로드·정규화")

            clip_paths: list[str] = []
            for i, clip in enumerate(req.clips):
                src = os.path.join(tmpdir, f"clip_src_{i}.mp4")
                await asyncio.to_thread(r2.download, clip.key, src)
                await asyncio.to_thread(_validate_clip_duration, src)

                normalized = os.path.join(tmpdir, f"clip_norm_{i}.mp4")
                await asyncio.to_thread(
                    _normalize_and_watermark_clip,
                    src,
                    clip.location_text,
                    clip.captured_at,
                    normalized,
                )
                clip_paths.append(normalized)

            bgm_path: str | None = None
            if req.bgm_key:
                bgm_path = os.path.join(tmpdir, "bgm.mp3")
                await asyncio.to_thread(r2.download, req.bgm_key, bgm_path)

            job_store.update(job_id, progress=50, step_message="영상 합성")
            out_path = os.path.join(tmpdir, "output.mp4")
            await asyncio.to_thread(_composite_clips, clip_paths, bgm_path, out_path)

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
