"""
Presigned URL shape.

Regression test for a silent misconfiguration: boto3 will happily build a
presigned URL against the global S3 host while signing it for a specific
region. Nothing raises - the URL simply gets a 307 from S3 and every upload
fails. The only place this is visible is the hostname, so assert on it.
"""
import os

import boto3
import pytest
from botocore.config import Config


@pytest.fixture
def client():
    return boto3.client(
        "s3",
        region_name="eu-west-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        aws_access_key_id="AKIA_TEST",
        aws_secret_access_key="secret",
    )


def test_presigned_url_uses_the_regional_host(client):
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": "sdc-lake-dev-space-demo", "Key": "sales/a.txt"},
        ExpiresIn=60,
    )
    host = url.split("//", 1)[1].split("/", 1)[0]
    assert host == "sdc-lake-dev-space-demo.s3.eu-west-1.amazonaws.com", (
        f"presigned URL points at {host!r}; a global host with a regional "
        "signature causes a 307 TemporaryRedirect on upload"
    )


def test_signature_region_matches_the_host(client):
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": "sdc-lake-dev-space-demo", "Key": "sales/a.txt"},
        ExpiresIn=60,
    )
    assert "eu-west-1%2Fs3%2Faws4_request" in url
