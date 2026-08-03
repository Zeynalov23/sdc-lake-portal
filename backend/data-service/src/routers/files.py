"""
Files router.
GET  /spaces/:id/files           — list objects in space
GET  /spaces/:id/files/download  — presigned download URL
POST /spaces/:id/files/upload    — presigned upload URL
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.utils.auth import get_current_user
from src.utils      import dynamo
from src.utils      import s3 as s3_util

router = APIRouter()
logger = logging.getLogger(__name__)


class UploadRequest(BaseModel):
    key:          str
    content_type: str = "application/octet-stream"


@router.get("/{space_id}/files")
def list_files(
    space_id: str,
    user:     Annotated[dict, Depends(get_current_user)],
    prefix:   str = Query(default="", description="Filter by prefix"),
):
    """List all objects in a space bucket via the user's access point."""
    access_point_arn = _get_access_point(user, space_id)

    objects = s3_util.list_objects(access_point_arn, prefix)

    return {
        "spaceId": space_id,
        "prefix":  prefix,
        "files":   objects,
        "count":   len(objects),
    }


@router.get("/{space_id}/files/download")
def get_download_url(
    space_id: str,
    key:      str,
    user:     Annotated[dict, Depends(get_current_user)],
):
    """Generate a presigned GET URL for downloading a file."""
    access_point_arn = _get_access_point(user, space_id)

    url = s3_util.generate_presigned_download_url(access_point_arn, key)

    return {
        "url":       url,
        "key":       key,
        "expiresIn": 3600,
    }


@router.post("/{space_id}/files/upload")
def get_upload_url(
    space_id: str,
    body:     UploadRequest,
    user:     Annotated[dict, Depends(get_current_user)],
):
    """
    Generate a presigned PUT URL for uploading a file.
    Writers only — readers get 403.
    """
    membership = _get_membership(user, space_id)

    if membership.get("role") != "writer":
        raise HTTPException(
            status_code=403,
            detail="Read-only access — cannot upload to this space",
        )

    access_point_arn = membership.get("accessPointArn")
    url = s3_util.generate_presigned_upload_url(
        access_point_arn, body.key, body.content_type
    )

    return {
        "url":         url,
        "key":         body.key,
        "method":      "PUT",
        "contentType": body.content_type,
        "expiresIn":   3600,
    }


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def _get_membership(user: dict, space_id: str) -> dict:
    membership = dynamo.get_membership(user["userId"], space_id)
    if not membership or membership.get("status") != "READY":
        raise HTTPException(status_code=403, detail="Access denied")
    return membership


def _get_access_point(user: dict, space_id: str) -> str:
    membership       = _get_membership(user, space_id)
    access_point_arn = membership.get("accessPointArn")
    if not access_point_arn:
        raise HTTPException(
            status_code=500,
            detail="Access point not provisioned yet",
        )
    return access_point_arn
