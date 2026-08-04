from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from auto_video_sub_application.ports import ObjectMetadata, SignedUpload
from auto_video_sub_domain import ValidationError
from botocore.client import Config
from botocore.exceptions import ClientError


class S3ObjectStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        public_endpoint: str,
        bucket: str,
        region: str,
        access_key: str,
        secret_key: str,
    ) -> None:
        common: dict[str, Any] = {
            "service_name": "s3",
            "region_name": region,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        self._client = boto3.client(endpoint_url=endpoint, **common)
        self._public_signer = boto3.client(endpoint_url=public_endpoint, **common)
        self._bucket = bucket

    @staticmethod
    def _ttl_seconds(expires_at: datetime) -> int:
        return max(1, min(3600, int((expires_at - datetime.now(UTC)).total_seconds())))

    def sign_upload(
        self,
        *,
        object_key: str,
        content_type: str,
        byte_size: int,
        expires_at: datetime,
    ) -> SignedUpload:
        url = self._public_signer.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": object_key,
                "ContentType": content_type,
                "ContentLength": byte_size,
            },
            ExpiresIn=self._ttl_seconds(expires_at),
        )
        return SignedUpload(
            url=url,
            method="PUT",
            headers={"content-type": content_type},
            expires_at=expires_at,
        )

    async def seal_upload(
        self,
        *,
        staging_key: str,
        sealed_key: str,
        expected_size: int,
        expected_content_type: str,
    ) -> ObjectMetadata:
        return await asyncio.to_thread(
            self._seal_upload_sync,
            staging_key,
            sealed_key,
            expected_size,
            expected_content_type,
        )

    def _seal_upload_sync(
        self,
        staging_key: str,
        sealed_key: str,
        expected_size: int,
        expected_content_type: str,
    ) -> ObjectMetadata:
        metadata = self._head_or_none(staging_key)
        if metadata is None:
            sealed = self._head_or_none(sealed_key)
            if sealed is None:
                raise ValidationError("Uploaded object was not found", code="UPLOAD_OBJECT_MISSING")
            self._validate_metadata(sealed, expected_size, expected_content_type)
            return sealed
        self._validate_metadata(metadata, expected_size, expected_content_type)
        self._client.copy_object(
            Bucket=self._bucket,
            Key=sealed_key,
            CopySource={"Bucket": self._bucket, "Key": staging_key},
            ContentType=expected_content_type,
            MetadataDirective="REPLACE",
        )
        sealed = self._head_or_none(sealed_key)
        if sealed is None:
            raise RuntimeError("sealed upload was not visible after copy")
        self._validate_metadata(sealed, expected_size, expected_content_type)
        self._client.delete_object(Bucket=self._bucket, Key=staging_key)
        return sealed

    @staticmethod
    def _validate_metadata(
        metadata: ObjectMetadata, expected_size: int, expected_content_type: str
    ) -> None:
        if metadata.byte_size != expected_size:
            raise ValidationError(
                "Uploaded object size does not match its declaration",
                code="UPLOAD_SIZE_MISMATCH",
            )
        if metadata.content_type.casefold() != expected_content_type.casefold():
            raise ValidationError(
                "Uploaded object type does not match its declaration",
                code="UPLOAD_TYPE_MISMATCH",
            )

    def _head_or_none(self, object_key: str) -> ObjectMetadata | None:
        try:
            response = self._client.head_object(Bucket=self._bucket, Key=object_key)
        except ClientError as error:
            code = str(error.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return ObjectMetadata(
            byte_size=int(response["ContentLength"]),
            content_type=str(response.get("ContentType", "application/octet-stream")),
            etag=str(response.get("ETag")) if response.get("ETag") else None,
        )

    async def object_metadata(self, object_key: str) -> ObjectMetadata:
        metadata = await asyncio.to_thread(self._head_or_none, object_key)
        if metadata is None:
            raise ValidationError("Object was not found", code="STORAGE_OBJECT_MISSING")
        return metadata

    async def download_file(self, object_key: str, destination: Path) -> None:
        await asyncio.to_thread(
            self._client.download_file,
            self._bucket,
            object_key,
            str(destination),
        )

    async def upload_file(self, source: Path, object_key: str, content_type: str) -> ObjectMetadata:
        await asyncio.to_thread(
            self._client.upload_file,
            str(source),
            self._bucket,
            object_key,
            ExtraArgs={"ContentType": content_type},
        )
        return await self.object_metadata(object_key)

    async def delete_object(self, object_key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=object_key)

    def sign_download(self, *, object_key: str, expires_at: datetime) -> str:
        return str(
            self._public_signer.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": object_key},
                ExpiresIn=self._ttl_seconds(expires_at),
            )
        )
