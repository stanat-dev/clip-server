from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    port: int = 8000
    internal_secret: str = "change-me"

    r2_endpoint_url: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str = "stanat"

    watermark_font_path: str = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

    # Job 상태 저장소. Spring 쪽과 동일한 Redis 인스턴스를 공유한다 (env var 이름도 맞춤).
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""


settings = Settings()
