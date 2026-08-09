"""
Files router.
GET  /spaces/:id/files           — list one page of objects in a space prefix
GET  /spaces/:id/files/download  — presigned download URL
POST /spaces/:id/files/upload    — presigned upload URL
"""
import logging
import os
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.utils.auth import get_current_user
from src.utils.authz import SpacePermission, require_space_permission
from src.utils import s3 as s3_util

router = APIRouter()
logger = logging.getLogger(__name__)

_DATA_BUCKET = os.environ["S3_BUCKET"]
_MAX_PAGE_SIZE = 100


class UploadRequest(BaseModel):
    key: str
    content_type: str = "application/octet-stream"


@router.get("/{space_id}/files")
def list_files(
    space_id: str,
    user: Annotated[dict, Depends(get_current_user)],
    prefix: str = Query(default="", description="Relative prefix inside the space"),
    continuation_token: str | None = Query(default=None, alias="continuationToken"),
):
    """List one page of objects from the user's authorized space prefix."""
    require_space_permission(user["userId"], space_id, SpacePermission.READ)

    space_prefix = _space_prefix(space_id)
    requested_prefix = _build_authorized_key(space_prefix, prefix, allow_empty=True)

    result = s3_util.list_objects(
        bucket_name=_DATA_BUCKET,
        prefix=requested_prefix,
        continuation_token=continuation_token,
        max_keys=_MAX_PAGE_SIZE,
    )

    files = [
        {
            **obj,
            "key": _relative_key(space_prefix, obj["key"]),
        }
        for obj in result["objects"]
    ]

    return {
        "spaceId": space_id,
        "prefix": prefix,
        "files": files,
        "count": len(files),
        "nextContinuationToken": result["nextToken"],
        "isTruncated": result["isTruncated"],
    }


@router.get("/{space_id}/files/download")
def get_download_url(
    space_id: str,
    key: str,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Generate a presigned GET URL for one file inside an authorized space."""
    require_space_permission(user["userId"], space_id, SpacePermission.READ)

    object_key = _build_authorized_key(_space_prefix(space_id), key)
    url = s3_util.generate_presigned_download_url(_DATA_BUCKET, object_key)

    return {
        "url": url,
        "key": key,
        "expiresIn": 3600,
    }


@router.post("/{space_id}/files/upload")
def get_upload_url(
    space_id: str,
    body: UploadRequest,
    user: Annotated[dict, Depends(get_current_user)],
):
    """Generate a presigned PUT URL. Requires space-level write permission."""
    require_space_permission(user["userId"], space_id, SpacePermission.WRITE)

    object_key = _build_authorized_key(_space_prefix(space_id), body.key)
    url = s3_util.generate_presigned_upload_url(
        _DATA_BUCKET,
        object_key,
        body.content_type,
    )

    return {
        "url": url,
        "key": body.key,
        "method": "PUT",
        "contentType": body.content_type,
        "expiresIn": 3600,
    }


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def _space_prefix(space_id: str) -> str:
    """The backend, never the client, owns the authorization boundary."""
    return f"spaces/{space_id}/"


def _build_authorized_key(
    space_prefix: str,
    relative_key: str,
    *,
    allow_empty: bool = False,
) -> str:
    """Build an S3 key beneath the backend-owned space prefix."""
    if relative_key == "":
        if allow_empty:
            return space_prefix
        raise HTTPException(status_code=400, detail="Object key cannot be empty")

    path = PurePosixPath(relative_key)

    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(status_code=400, detail="Invalid object key")

    normalized = path.as_posix()
    if not normalized or normalized == ".":
        if allow_empty:
            return space_prefix
        raise HTTPException(status_code=400, detail="Invalid object key")

    return f"{space_prefix}{normalized}"


def _relative_key(space_prefix: str, object_key: str) -> str:
    """Hide the internal authorization prefix from API consumers."""
    if not object_key.startswith(space_prefix):
        raise RuntimeError("S3 returned an object outside the requested space prefix")
    return object_key[len(space_prefix):]
