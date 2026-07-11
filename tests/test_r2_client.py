import pytest
from unittest.mock import MagicMock, patch

from app.storage.r2_client import R2Client


@patch("app.storage.r2_client.boto3.client")
def test_download_calls_get_object(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    client = R2Client(
        endpoint_url="https://test.r2.cloudflarestorage.com",
        access_key_id="key",
        secret_access_key="secret",
        bucket_name="test-bucket",
    )
    client.download("clips/abc.mp4", "/tmp/abc.mp4")
    mock_s3.download_file.assert_called_once_with("test-bucket", "clips/abc.mp4", "/tmp/abc.mp4")


@patch("app.storage.r2_client.boto3.client")
def test_upload_returns_key_url(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    client = R2Client(
        endpoint_url="https://test.r2.cloudflarestorage.com",
        access_key_id="key",
        secret_access_key="secret",
        bucket_name="test-bucket",
    )
    url = client.upload("/tmp/out.mp4", "renders/out.mp4", "video/mp4")
    mock_s3.upload_file.assert_called_once_with(
        "/tmp/out.mp4", "test-bucket", "renders/out.mp4",
        ExtraArgs={"ContentType": "video/mp4"}
    )
    assert url == "renders/out.mp4"
