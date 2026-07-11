from typing import Any

import boto3


class R2Client:
    def __init__(
        self,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
    ):
        self._bucket = bucket_name
        self._s3: Any = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def download(self, key: str, dest_path: str) -> None:
        self._s3.download_file(self._bucket, key, dest_path)

    def upload(self, src_path: str, key: str, content_type: str) -> str:
        self._s3.upload_file(
            src_path,
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return key


def make_r2_client() -> R2Client:
    from app.config import settings

    return R2Client(
        endpoint_url=settings.r2_endpoint_url,
        access_key_id=settings.r2_access_key_id,
        secret_access_key=settings.r2_secret_access_key,
        bucket_name=settings.r2_bucket_name,
    )
