"""
Shared S3 utilities.
Import this instead of duplicating boto3 setup across routers.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import boto3
from botocore.client import Config

logger = logging.getLogger(__name__)

# ── Config from environment ────────────────────────────────────────
S3_ENDPOINT    = os.getenv("S3_ENDPOINT")
S3_BUCKET      = os.getenv("S3_BUCKET")
S3_ACCESS_KEY  = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY  = os.getenv("S3_SECRET_KEY")
S3_REGION      = os.getenv("S3_REGION", "eu-central-1")
S3_PUBLIC_BASE = os.getenv("S3_PUBLIC_BASE", "")

# ── Allowed upload MIME types ──────────────────────────────────────
ALLOWED_IMG: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png":  "png",
    "image/webp": "webp",
}


def get_client() -> "boto3.client":
    """Return a configured S3 client."""
    kwargs: dict = dict(
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name=S3_REGION,
    )
    if S3_ENDPOINT:
        kwargs["endpoint_url"] = S3_ENDPOINT
    return boto3.client("s3", **kwargs)


def presign(key: Optional[str], expires_in: int = 3600) -> Optional[str]:
    """
    Return a public URL for *key*.

    Resolution order:
    1. Empty / None  → None
    2. Already a full URL → return as-is
    3. S3_PUBLIC_BASE configured → simple string concat (no signing)
    4. Otherwise → generate a pre-signed URL via boto3
    """
    if not key:
        return None
    if key.startswith("http"):
        return key
    if S3_PUBLIC_BASE:
        return f"{S3_PUBLIC_BASE.rstrip('/')}/{key.lstrip('/')}"
    try:
        return get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key.lstrip("/")},
            ExpiresIn=expires_in,
        )
    except Exception as exc:
        logger.error("S3 presign error for key=%s: %s", key, exc)
        return key  # fall back to raw key rather than returning None


def upload_fileobj(fileobj, key: str, content_type: str) -> None:
    """Upload a file-like object to S3. Raises on failure."""
    get_client().upload_fileobj(
        Fileobj=fileobj,
        Bucket=S3_BUCKET,
        Key=key,
        ExtraArgs={"ContentType": content_type},
    )


def delete_object(key: str) -> None:
    """Delete an object from S3. Silently ignores errors."""
    if not key or key.startswith("http"):
        return
    try:
        get_client().delete_object(Bucket=S3_BUCKET, Key=key)
    except Exception as exc:
        logger.warning("S3 delete error for key=%s: %s", key, exc)
