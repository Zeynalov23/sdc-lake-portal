"""
Files router.
GET  /spaces/:id/files           — list one page of objects in a space bucket
GET  /spaces/:id/files/download  — presigned download URL
POST /spaces/:id/files/upload    — presigned upload URL
"""
import logging
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.utils.auth import get_current_user
from src.utils import authz, dynamo
from src.utils import s3 as s3_util

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_PAGE_SIZE = 100


class UploadRequest(BaseModel):
    key: str
    content_type: str = "application/octet-stream"


@router.get("/{space_id}/files")
def list_files(
    space_id: str,
    user: Annotated[dict, Depends(get_current_user)],
    prefix: str = Query(default="", description="Relative prefix inside the space bucket"),
    continuation_token: str | None = Query(default=None, alias="continuationToken"),
):
    """List one page of objects from a space bucket."""
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.READ
    )
    bucket_name = _get_bucket_name(space_id)
    requested_prefix = _validate_relative_key(prefix, allow_empty=True)

    result = s3_util.list_objects(
        bucket_name=bucket_name,
        prefix=requested_prefix,
        continuation_token=continuation_token,
        max_keys=_MAX_PAGE_SIZE,
    )

    return {
        "spaceId": space_id,
        "prefix": prefix,
        "files": result["objects"],
        "count": len(result["objects"]),
        "nextContinuationToken": result["nextToken"],
        "isTruncated": result["isTruncated"],
    }


@router.get("/{space_id}/files/download")
def get_download_url(
    space_id: str,
    key: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Generate a presigned GET URL for one file in a space bucket."""
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.READ
    )
    bucket_name = _get_bucket_name(space_id)
    object_key = _validate_relative_key(key)

    url = s3_util.generate_presigned_download_url(bucket_name, object_key)

    return {
        "url": url,
        "key": object_key,
        "expiresIn": 3600,
    }


@router.post("/{space_id}/files/upload")
def get_upload_url(
    space_id: str,
    body: UploadRequest,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Generate a presigned PUT URL. Space WRITE permission is required."""
    authz.require_space_permission(
        user["userId"], space_id, authz.SpacePermission.WRITE
    )
    bucket_name = _get_bucket_name(space_id)
    object_key = _validate_relative_key(body.key)

    url = s3_util.generate_presigned_upload_url(
        bucket_name,
        object_key,
        body.content_type,
    )

    return {
        "url": url,
        "key": object_key,
        "method": "PUT",
        "contentType": body.content_type,
        "expiresIn": 3600,
    }


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def _get_bucket_name(space_id: str) -> str:
    metadata = dynamo.get_space_metadata(space_id)
    if not metadata or metadata.get("status") != "READY":
        raise HTTPException(status_code=404, detail="Space not found or not ready")

    bucket_name = metadata.get("bucketName")
    if not bucket_name:
        raise HTTPException(status_code=500, detail="Space bucket is not configured")
    return bucket_name


def _validate_relative_key(relative_key: str, *, allow_empty: bool = False) -> str:
    """Accept only S3 keys relative to the already-authorized space bucket."""
    if relative_key == "":
        if allow_empty:
            return ""
        raise HTTPException(status_code=400, detail="Object key cannot be empty")

    path = PurePosixPath(relative_key)
    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(status_code=400, detail="Invalid object key")

    normalized = path.as_posix()
    if not normalized or normalized == ".":
        if allow_empty:
            return ""
        raise HTTPException(status_code=400, detail="Invalid object key")

    return normalized
