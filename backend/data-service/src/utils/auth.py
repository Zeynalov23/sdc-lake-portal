"""
Auth utilities.
Verifies the Cognito ID token (RS256, signed against the User Pool's JWKS)
sent as a Bearer token. This is the actual trust boundary for the app —
the frontend's own decoding of its session cookie is display-only.
"""
import os

import jwt
from fastapi import Header, HTTPException

_REGION        = os.environ.get("COGNITO_REGION", "eu-west-1")
_USER_POOL_ID  = os.environ.get("COGNITO_USER_POOL_ID", "eu-west-1_TjHI7KEwu")
_APP_CLIENT_ID = os.environ.get("COGNITO_APP_CLIENT_ID", "71j6ijo9v8ev1ejiinqtnfag61")
_ISSUER        = f"https://cognito-idp.{_REGION}.amazonaws.com/{_USER_POOL_ID}"
_JWKS_URL      = f"{_ISSUER}/.well-known/jwks.json"

_jwks_client = jwt.PyJWKClient(_JWKS_URL, cache_keys=True, lifespan=3600)


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """
    Dependency that verifies the Bearer ID token and extracts user identity.
    Raises 401 on any missing/invalid/expired/mis-signed token.
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
            audience=_APP_CLIENT_ID,
            issuer=_ISSUER,
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    if claims.get("token_use") != "id":
        raise HTTPException(status_code=401, detail="Expected an ID token")

    return {
        "userId": claims["sub"],
        "email":  claims.get("email"),
    }
