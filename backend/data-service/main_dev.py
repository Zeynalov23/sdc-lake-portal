"""
Local development entry point. NOT used in the cluster.

Getting a real Entra ID token requires the browser login flow, which is
awkward before the frontend exists. This module starts the same app but
replaces the auth dependency with a fake user taken from a header, so you
can exercise the API with curl.

The override lives here rather than behind a flag inside auth.py on purpose:
production runs `main:app` and there is no code path in it that can skip
token verification, whatever the environment variables say. A misconfigured
env var cannot turn authentication off in the cluster, because the cluster
never imports this file.

Run:
    uvicorn main_dev:app --host 0.0.0.0 --port 8000
    curl -H "X-Dev-User: alice" localhost:8000/spaces
"""
import logging
import os

from fastapi import Header

from main import app
from src.utils.auth import get_current_user

logger = logging.getLogger(__name__)

_DEFAULT_USER = os.environ.get("DEV_USER_ID", "dev-user-1")
_DEFAULT_EMAIL = os.environ.get("DEV_USER_EMAIL", "dev@example.invalid")


def _fake_user(
    x_dev_user: str = Header(default=None, alias="X-Dev-User"),
    x_dev_email: str = Header(default=None, alias="X-Dev-Email"),
) -> dict:
    """
    Impersonate any user by header. Being able to switch identity freely is
    the point: it is how you test that a consumer really cannot write, or
    that a product consumer really cannot read another folder.
    """
    return {
        "userId": x_dev_user or _DEFAULT_USER,
        "email": x_dev_email or _DEFAULT_EMAIL,
        "name": "Local Dev User",
    }


app.dependency_overrides[get_current_user] = _fake_user

logger.warning(
    "AUTHENTICATION DISABLED - local dev entry point. "
    "Identity comes from the X-Dev-User header."
)


# Microsoft Graph needs a client secret and admin consent, which is more setup
# than a local run should require. Fake the directory so member endpoints are
# usable with curl: any address resolves to a stable id derived from it, which
# is enough to exercise the grant logic.
if os.environ.get("DEV_FAKE_GRAPH", "true").lower() == "true":
    from src.utils import graph as _graph

    def _fake_find_user_by_email(email: str) -> dict:
        email = email.strip().lower()
        local_part = email.split("@")[0]
        return {
            "oid": f"dev-{local_part}",
            "email": email,
            "name": local_part.replace(".", " ").title(),
        }

    _graph.find_user_by_email = _fake_find_user_by_email
    logger.warning("DIRECTORY LOOKUP FAKED - emails resolve to dev-<localpart>")
