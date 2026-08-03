"""
Input validation helpers.
Raises ValueError with a descriptive message on failure.
"""
import re

_SPACE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{2,62}[a-z0-9]$")
_VALID_TIERS   = {"standard", "premium"}
_VALID_ROLES   = {"writer", "reader"}
_VALID_EVENTS  = {
    "s3:ObjectCreated:*",
    "s3:ObjectRemoved:*",
    "s3:ObjectRestore:*",
}


def require_fields(body: dict, fields: list[str]) -> None:
    missing = [f for f in fields if not body.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def validate_space_name(name: str) -> None:
    if not _SPACE_NAME_RE.match(name):
        raise ValueError(
            "Space name must be 4-64 characters, "
            "lowercase letters, numbers, and hyphens only. "
            "Must start and end with a letter or number."
        )


def validate_tier(tier: str) -> None:
    if tier not in _VALID_TIERS:
        raise ValueError(f"Invalid tier '{tier}'. Must be one of: {', '.join(_VALID_TIERS)}")


def validate_role(role: str) -> None:
    if role not in _VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of: {', '.join(_VALID_ROLES)}")


def validate_events(events: list[str]) -> None:
    invalid = [e for e in events if e not in _VALID_EVENTS]
    if invalid:
        raise ValueError(f"Invalid event types: {', '.join(invalid)}")
