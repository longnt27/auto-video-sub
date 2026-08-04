from __future__ import annotations

import boto3
from botocore.client import Config

from auto_video_sub_infrastructure.settings import get_settings


def _cors_rules(origins: tuple[str, ...]) -> list[dict[str, object]]:
    return [
        {
            "AllowedHeaders": ["content-type"],
            "AllowedMethods": ["GET", "HEAD", "PUT"],
            "AllowedOrigins": [origin],
            "ExposeHeaders": ["etag"],
            "MaxAgeSeconds": 600,
        }
        for origin in origins
    ]


def run() -> None:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.object_store_endpoint,
        region_name=settings.object_store_region,
        aws_access_key_id=settings.object_store_access_key,
        aws_secret_access_key=settings.object_store_secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    client.put_bucket_cors(
        Bucket=settings.object_store_bucket,
        CORSConfiguration={"CORSRules": _cors_rules(settings.cors_allowed_origins)},
    )


if __name__ == "__main__":
    run()
