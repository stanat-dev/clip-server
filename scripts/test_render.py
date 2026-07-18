#!/usr/bin/env python
"""로컬 R2 테스트 버킷으로 clip-server 렌더 파이프라인을 end-to-end 검증하는 스크립트.

모바일 웹/앱이 아직 이 서버를 호출하지 않는 상태에서, 로컬 mp4 클립 파일들을
.env에 설정된 R2 버킷에 업로드하고 POST /internal/renders를 호출한 뒤
완료될 때까지 폴링하고, 완료되면 결과 mp4를 R2에서 받아와 로컬에 저장한다.

사용 예 (로컬 파일 업로드):
    python scripts/test_render.py \
        --clip samples/clip1.mp4 "강남역" \
        --clip samples/clip2.mp4 "한강공원" \
        --out render_result.mp4

사용 예 (이미 R2 original-clips/ 에 올려둔 클립 재사용, 업로드 생략):
    python scripts/test_render.py \
        --clip-key original-clips/xxx/clip1.mp4 "강남역" \
        --clip-key original-clips/xxx/clip2.mp4 "한강공원" \
        --out render_result.mp4

--clip과 --clip-key는 섞어 쓸 수 있으며, 명령줄에 적은 순서대로 합성된다.

사전 조건:
    - uvicorn app.main:app 이 로컬에서 실행 중이어야 함 (기본 http://localhost:8000)
    - .env에 실제 R2 테스트 버킷 자격증명이 채워져 있어야 함
    - 클립 파일은 5초 이내 mp4 여야 함 (render_service의 길이 검증 통과 조건)
"""

import argparse
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

from app.storage.r2_client import make_r2_client

KST = timezone(timedelta(hours=9))


class _ClipAction(argparse.Action):
    """--clip(로컬 업로드)과 --clip-key(기존 R2 키 재사용)를 같은 리스트에
    명령줄 순서대로 쌓기 위한 커스텀 액션. 서브클래스에서 kind를 지정한다."""

    kind: str = ""

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.append((self.kind, values[0], values[1]))
        setattr(namespace, self.dest, items)


class _ClipFileAction(_ClipAction):
    kind = "file"


class _ClipKeyAction(_ClipAction):
    kind = "key"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="clip-server 로컬 렌더 테스트")
    parser.add_argument(
        "--clip",
        nargs=2,
        action=_ClipFileAction,
        metavar=("FILE", "LOCATION_TEXT"),
        dest="clip_items",
        help="로컬 클립 파일 경로와 장소명 (R2에 업로드 후 사용, 여러 번 지정 가능)",
    )
    parser.add_argument(
        "--clip-key",
        nargs=2,
        action=_ClipKeyAction,
        metavar=("R2_KEY", "LOCATION_TEXT"),
        dest="clip_items",
        help="이미 R2에 올라가 있는 클립의 오브젝트 키와 장소명 (업로드 생략, 여러 번 지정 가능)",
    )
    parser.add_argument("--bgm", help="로컬 BGM mp3 파일 경로 (선택, 업로드함)")
    parser.add_argument("--bgm-key", help="이미 R2에 올라가 있는 BGM 오브젝트 키 (선택, 업로드 생략)")
    parser.add_argument("--trip-id", type=int, default=1)
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--render-id", type=int, default=None)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--out", default="render_result.mp4", help="결과 저장 경로")
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()
    if not args.clip_items:
        parser.error("최소 한 개 이상의 --clip 또는 --clip-key 가 필요합니다")
    if args.render_id is None:
        args.render_id = int(time.time())
    return args


def build_clips(r2, clip_items: list[tuple[str, str, str]], run_tag: str) -> list[dict]:
    clips = []
    now = datetime.now(KST)
    for i, (kind, ref, location_text) in enumerate(clip_items):
        if kind == "key":
            key = ref
            print(f"[재사용] {key}")
        else:
            if not os.path.isfile(ref):
                raise FileNotFoundError(f"클립 파일을 찾을 수 없음: {ref}")
            key = f"original-clips/test/{run_tag}/clip_{i}.mp4"
            print(f"[업로드] {ref} -> {key}")
            r2.upload(ref, key, "video/mp4")
        captured_at = (now + timedelta(seconds=i)).isoformat()
        clips.append({"key": key, "location_text": location_text, "captured_at": captured_at})
    return clips


def resolve_bgm(r2, bgm_path: str | None, bgm_key: str | None, run_tag: str) -> str | None:
    if bgm_key:
        print(f"[재사용] {bgm_key}")
        return bgm_key
    if not bgm_path:
        return None
    if not os.path.isfile(bgm_path):
        raise FileNotFoundError(f"BGM 파일을 찾을 수 없음: {bgm_path}")
    key = f"original-clips/test/{run_tag}/bgm.mp3"
    print(f"[업로드] {bgm_path} -> {key}")
    r2.upload(bgm_path, key, "audio/mpeg")
    return key


def main() -> None:
    args = parse_args()
    run_tag = uuid.uuid4().hex[:8]

    r2 = make_r2_client()
    clips = build_clips(r2, args.clip_items, run_tag)
    bgm_key = resolve_bgm(r2, args.bgm, args.bgm_key, run_tag)

    payload = {
        "trip_id": args.trip_id,
        "user_id": args.user_id,
        "render_id": args.render_id,
        "clips": clips,
        "bgm_key": bgm_key,
    }

    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        print("[요청] POST /internal/renders")
        resp = client.post("/internal/renders", json=payload)
        resp.raise_for_status()
        job_id = resp.json()["data"]["job_id"]
        print(f"[job_id] {job_id}")

        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            resp = client.get(f"/internal/renders/{job_id}")
            resp.raise_for_status()
            status = resp.json()["data"]
            print(f"[상태] {status['status']} {status['progress']}% - {status['step_message']}")

            if status["status"] == "DONE":
                result_key = status["result_key"]
                print(f"[다운로드] {result_key} -> {args.out}")
                r2.download(result_key, args.out)
                print(f"완료: {args.out}")
                return

            if status["status"] == "FAILED":
                print(f"실패: {status['error']}")
                sys.exit(1)

            time.sleep(args.poll_interval)

        print("타임아웃: 렌더가 제한 시간 내에 끝나지 않음")
        sys.exit(1)


if __name__ == "__main__":
    main()
