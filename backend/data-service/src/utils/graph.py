from __future__ import annotations

"""
Microsoft Graph — turning an email address into an Entra object ID.

When an owner grants access they type an email. Grants are stored by `oid`,
so we look the user up in the tenant directory first. This uses the client
credentials flow: the service authenticates as itself, not on behalf of the
signed-in user, which is why the app registration needs the APPLICATION
permission `User.Read.All` with admin consent.

The client secret is read from the environment. Locally that comes from a
gitignored .env file; in the cluster it will come from External Secrets.
"""
import os
import threading
import time

import httpx
from fastapi import HTTPException

_TENANT_ID = os.environ["ENTRA_TENANT_ID"]
_CLIENT_ID = os.environ["ENTRA_CLIENT_ID"]
_CLIENT_SECRET = os.environ["ENTRA_CLIENT_SECRET"]

_TOKEN_URL = f"https://login.microsoftonline.com/{_TENANT_ID}/oauth2/v2.0/token"
_GRAPH_SCOPE = "https://graph.microsoft.com/.default"
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Graph tokens last about an hour. Cache it rather than fetching one per
# request, and refresh a minute early to avoid using a token that expires
# in flight.
_lock = threading.Lock()
_cached_token: str | None = None
_expires_at: float = 0.0


def _get_token() -> str:
    global _cached_token, _expires_at

    with _lock:
        if _cached_token and time.time() < _expires_at:
            return _cached_token

        response = httpx.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "scope": _GRAPH_SCOPE,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()

        _cached_token = payload["access_token"]
        _expires_at = time.time() + payload.get("expires_in", 3600) - 60
        return _cached_token


def find_user_by_email(email: str) -> dict:
    """
    Look up one user in the tenant by email.
    Returns {"oid", "email", "name"}. Raises 404 if there is no such user.

    We query on both userPrincipalName and mail because they are not always
    the same value — guest users in particular have a UPN that looks nothing
    like their email address.
    """
    email = email.strip().lower()
    token = _get_token()

    response = httpx.get(
        f"{_GRAPH_BASE}/users",
        params={
            "$filter": f"userPrincipalName eq '{email}' or mail eq '{email}'",
            "$select": "id,displayName,mail,userPrincipalName",
            "$top": "2",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )

    if response.status_code == 403:
        raise HTTPException(
            status_code=500,
            detail="Directory lookup not permitted — check admin consent",
        )
    response.raise_for_status()

    users = response.json().get("value", [])
    if not users:
        raise HTTPException(
            status_code=404, detail=f"No user in the directory for {email}"
        )
    if len(users) > 1:
        # Ambiguous: refuse rather than pick one and grant the wrong person.
        raise HTTPException(
            status_code=409, detail=f"Multiple directory users match {email}"
        )

    user = users[0]
    return {
        "oid": user["id"],
        "email": user.get("mail") or user.get("userPrincipalName"),
        "name": user.get("displayName"),
    }
