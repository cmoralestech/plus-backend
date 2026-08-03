"""Storage abstraction — local filesystem in dev, S3 in production."""
import asyncio
import logging
import os
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger("plus.storage")


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, data: bytes, filename: str) -> str:
        """Save file, return public URL."""

    @abstractmethod
    async def delete(self, filename: str) -> bool:
        """Delete a file. Returns True only if it is genuinely gone.

        Callers removing prohibited content rely on this answer: a silent
        failure leaves the file retrievable at its URL while the database row
        disappears, which looks like successful moderation and is not.
        """


class LocalStorage(StorageBackend):
    def __init__(self):
        self.upload_dir = Path(__file__).resolve().parent.parent.parent / "uploads"
        self.upload_dir.mkdir(exist_ok=True)

    async def save(self, data: bytes, filename: str) -> str:
        filepath = self.upload_dir / filename
        with open(filepath, "wb") as f:
            f.write(data)
        return f"/api/photos/file/{filename}"

    async def delete(self, filename: str) -> bool:
        filepath = self.upload_dir / filename
        try:
            if filepath.exists():
                os.remove(filepath)
            return True
        except OSError:
            logger.exception("[STORAGE] Failed to delete %s", filepath)
            return False


class S3Storage(StorageBackend):
    def __init__(self):
        self.bucket = settings.S3_BUCKET
        self.region = settings.S3_REGION
        endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3")
        self.client = boto3.client("s3", region_name=self.region, endpoint_url=endpoint_url)
        if endpoint_url:
            self.base_url = f"{endpoint_url}/{self.bucket}"
        else:
            self.base_url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com"

    async def save(self, data: bytes, filename: str) -> str:
        key = f"photos/{filename}"
        content_type = "image/jpeg"
        if filename.endswith(".png"):
            content_type = "image/png"
        elif filename.endswith(".webp"):
            content_type = "image/webp"

        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return f"{self.base_url}/{key}"

    async def delete(self, filename: str) -> bool:
        key = f"photos/{filename}"
        try:
            await asyncio.to_thread(
                self.client.delete_object, Bucket=self.bucket, Key=key
            )
            return True
        except ClientError:
            logger.exception("[STORAGE] Failed to delete %s from %s", key, self.bucket)
            return False


def get_storage() -> StorageBackend:
    import logging
    logger = logging.getLogger("plus.storage")
    if settings.S3_BUCKET:
        logger.info(f"[STORAGE] Using S3 bucket: {settings.S3_BUCKET}")
        return S3Storage()
    if settings.ENVIRONMENT == "production":
        logger.critical(
            "[STORAGE] S3_BUCKET not configured in production! "
            "Photos are stored on ephemeral disk and WILL BE LOST on deploy. "
            "Set S3_BUCKET, AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY."
        )
    else:
        logger.warning("[STORAGE] Using local filesystem (dev only)")
    return LocalStorage()


storage = get_storage()
