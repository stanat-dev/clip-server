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


settings = Settings()
