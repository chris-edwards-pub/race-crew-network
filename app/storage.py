from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from flask import current_app, url_for


def _use_s3() -> bool:
    """Return True when S3 storage is configured (BUCKET_NAME is set)."""
    return bool(current_app.config.get("BUCKET_NAME"))


def _get_client():
    """Return a boto3 S3 client configured for Lightsail Object Storage."""
    region = current_app.config["AWS_REGION"]
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
    )


def _get_upload_path(key: str) -> Path:
    """Resolve a storage key to a full local filesystem path.

    Raises ValueError if the resolved path escapes the upload directory
    (path traversal protection).
    """
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    base = Path(upload_folder)
    if not base.is_absolute():
        base = Path(current_app.root_path).parent / upload_folder
    full_path = (base / key).resolve()
    if not str(full_path).startswith(str(base.resolve())):
        raise ValueError("Invalid file path")
    return full_path


def upload_file(file, stored_filename: str) -> None:
    """Upload a file-like object to S3 or the local filesystem."""
    if _use_s3():
        bucket = current_app.config["BUCKET_NAME"]
        client = _get_client()
        client.upload_fileobj(file, bucket, stored_filename)
    else:
        full_path = _get_upload_path(stored_filename)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        file.save(full_path)


def get_file_url(stored_filename: str) -> str:
    """Return a URL for downloading a file.

    S3: presigned URL valid for 1 hour.
    Local: route URL served by the storage blueprint.
    """
    if _use_s3():
        bucket = current_app.config["BUCKET_NAME"]
        client = _get_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": stored_filename},
            ExpiresIn=3600,
        )
    return url_for("storage_bp.serve_file", filename=stored_filename)


def delete_file(stored_filename: str) -> None:
    """Delete a file from S3 or the local filesystem. Silently ignores missing files."""
    if _use_s3():
        bucket = current_app.config["BUCKET_NAME"]
        client = _get_client()
        try:
            client.delete_object(Bucket=bucket, Key=stored_filename)
        except ClientError:
            pass
    else:
        full_path = _get_upload_path(stored_filename)
        full_path.unlink(missing_ok=True)
