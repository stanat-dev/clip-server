# CLAUDE.md — StanAt Clip Server (Python)

> 이 파일은 자동 로드되는 **이정표**다. 긴 설계/구현 계획을 여기에 두지 않는다. 계획은 `docs/superpowers/plans/`를 참고한다.

## 1. 프로젝트 정체성

이 서버는 **StanAt Spring 백엔드의 내부 전용 Python 워커**다.  
외부 클라이언트(웹/앱)는 이 서버에 직접 접근하지 않는다.  
모든 요청은 `Spring → Python` 단방향으로만 흐른다.

담당하는 비동기 작업:

- **영상 합성** (S13~S14): 클립 파일들을 FFmpeg으로 합성해 최종 영상을 만들고 R2에 업로드한다.

## 2. 확정 기술 방향

- **Language**: Python 3.12+
- **Framework**: FastAPI 0.115+
- **Video**: ffmpeg-python (시스템 FFmpeg 필요)
- **Storage**: R2(Cloudflare) — boto3 S3-compatible API
- **Config**: pydantic-settings + `.env`
- **Test**: pytest, pytest-asyncio, httpx

## 3. 아키텍처 규칙(MUST)

- 모든 엔드포인트는 `/internal/` prefix를 사용한다. 외부 클라이언트가 직접 호출하는 구조가 아니다.
- 무거운 작업(FFmpeg 합성)은 **비동기 백그라운드 태스크**로 처리하고 `jobId` 기반 폴링을 제공한다.
- 클립은 촬영한 클라이언트(모바일 웹, 네이티브 앱 등)를 구분하지 않는다. API에 클라이언트 종류 필드를 두지 않고, 합성 전 `render_service._normalize_clip`으로 모든 클립을 동일 해상도/fps/코덱/픽셀 포맷으로 정규화해 하나의 코드 경로로 처리한다.
- 파일은 **R2에만** 저장한다. 로컬 파일은 `tempfile.TemporaryDirectory()` 안에서만 사용하고 완료 즉시 정리한다.
- Python 서버는 결과물의 **R2 오브젝트 키**만 Spring에 반환한다. Presigned URL 생성은 Spring이 담당한다.
- 응답 포맷: `{"success": true, "data": ...}` / 오류: `{"success": false, "error": {"code": ..., "message": ...}}`
- 예외는 `ClipServerException` → FastAPI exception handler 단일 흐름으로 처리한다.
- 환경변수는 `app/config.py`의 `Settings` 싱글턴으로 관리한다. 코드에 자격증명을 직접 쓰지 않는다.

## 4. Presigned URL 흐름 (Spring 연동)

```
[Python] 합성 완료 → R2 upload(key: "renders/{tripId}/{renderId}.mp4")
       → job status에 result_key 저장

[Spring] GET /internal/renders/{jobId} 폴링
       → status == DONE 이면 result_key 수신 → DB에 저장

[Client] GET /renders/{renderId} 요청
       → Spring이 R2 SDK로 Presigned URL 생성(TTL 설정) → 클라이언트에 반환

[Client] Presigned URL로 R2에서 직접 다운로드
```

Python이 presigned URL을 직접 생성하지 않는 이유: 생성 시점과 클라이언트 사용 시점 사이에 TTL이 만료될 수 있기 때문이다. Spring이 요청 시마다 신선한 URL을 발급한다.

## 5. 디렉터리 구조

```
app/
├── main.py          # FastAPI 앱, 라우터 등록
├── config.py        # Settings (pydantic-settings)
├── exceptions.py    # ClipServerException + handler
├── schemas/         # Pydantic 요청/응답 모델
├── routers/         # FastAPI 라우터 (render)
├── services/        # 비즈니스 로직 (render_service)
├── store/           # 인메모리 job 상태 저장소
└── storage/         # R2 클라이언트
tests/               # pytest 테스트
```

## 6. 작업별 참조 문서

| 작업                 | 먼저 읽을 문서                                     |
| -------------------- | -------------------------------------------------- |
| 기능/화면 흐름 파악  | `docs/feature-flow.md`                             |
| Spring API 연동 구조 | `docs/spring-api-spec.md`                          |
| 전체 구현 플랜       | `docs/superpowers/plans/2026-06-29-clip-server.md` |

## 7. 확정 결정

- 외부 클라이언트 직접 호출 없음 — Spring 내부망에서만 접근
- 비동기 작업 결과는 **R2 오브젝트 키** 반환, presigned URL은 Spring 담당
- 클립 길이 검증(5초 이내)은 `ffmpeg.probe()` 기반으로 `render_service` 내부에서 처리
- 클립은 웹/앱 등 촬영 클라이언트 구분 없이 합성 전 동일 스펙으로 정규화(`_normalize_clip`)한 뒤 concat한다 (모바일 웹의 webm/VP9+Opus, 네이티브 앱의 mp4/mov·H.264/HEVC 혼재 대응)
- 인메모리 job store 사용 (MVP); 영속성이 필요하면 Redis로 교체 결정

## 8. 문서 운영 원칙

- `CLAUDE.md`는 이정표와 확정 규칙만 담는다.
- 상세 구현 계획은 `docs/superpowers/plans/`에 둔다.
- Swagger/OpenAPI(`/docs`)와 코드가 Spring 서버 API 명세의 정본이다.

## 9. 코드 변경 시 필수 검증(MUST)

코드를 작성하거나 수정하는 작업의 마지막 단계에서는 **반드시 자동으로** 아래를 실행하고 결과를 확인한다. 사용자가 별도로 요청하지 않아도 매번 수행한다.

- 컴파일/타입 체크: `python -m py_compile <변경 파일>` 또는 프로젝트에 타입 체커가 설정되어 있으면 그것을 사용
- 테스트: `pytest tests/ -v` (전체 스위트가 오래 걸리면 최소한 변경과 관련된 테스트 파일)
- 빌드: `Dockerfile`을 변경했거나 배포 가능 여부를 확인해야 하는 경우 `docker build -t clip-server .`

실패하면 실패 원인을 먼저 분석해 코드를 고치고, 통과할 때까지 반복한다. 통과 여부를 확인하지 않은 채 "완료"라고 보고하지 않는다.
