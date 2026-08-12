from __future__ import annotations

"""
Authentication — Microsoft Entra ID.

The frontend (Next.js, confidential client) performs the OIDC code flow
against Entra and forwards the resulting ID token to this service as a
Bearer token. This service is the real trust boundary: it verifies the
signature against Entra's JWKS on every request.

We identify users by the `oid` claim — the Entra object ID. It is a GUID
that is unique and stable for the lifetime of the user in the tenant.
Email can change; oid cannot. Every grant in DynamoDB is keyed by oid.
"""
import os
import jwt
from fastapi import Header, HTTPException

_TENANT_ID = os.environ["ENTRA_TENANT_ID"]
_CLIENT_ID = os.environ["ENTRA_CLIENT_ID"]

# Entra v2.0 endpoints. The issuer must match exactly what is inside the
# token, otherwise verification fails.
_ISSUER = f"https://login.microsoftonline.com/{_TENANT_ID}/v2.0"
_JWKS_URL = f"https://login.microsoftonline.com/{_TENANT_ID}/discovery/v2.0/keys"

# Caches the signing keys so we do not fetch JWKS on every request.
# Entra rotates keys, so the cache has a lifetime rather than being permanent.
_jwks_client = jwt.PyJWKClient(_JWKS_URL, cache_keys=True, lifespan=3600)


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """
    FastAPI dependency. Verifies the Bearer ID token and returns the caller.
    Raises 401 for anything missing, expired, or wrongly signed.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ")

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=_CLIENT_ID,
            issuer=_ISSUER,
        )
    except jwt.PyJWTError as e:
        # Deliberately vague to the client, detailed in logs only.
        raise HTTPException(status_code=401, detail="Invalid token") from e

    oid = claims.get("oid")
    if not oid:
        # Should never happen for a tenant user, but never trust the token
        # to contain what you expect.
        raise HTTPException(status_code=401, detail="Token has no oid claim")

    # `preferred_username` is the usual email-shaped claim in Entra.
    # It is display-only here — authorisation never depends on it.
    # Returned as a dict with "userId" so the existing routers and authz
    # signatures stay unchanged. userId IS the Entra oid.
    return {
        "userId": oid,
        "email": claims.get("preferred_username") or claims.get("email"),
        "name": claims.get("name"),
    }
