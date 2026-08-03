"""
Write Lambda — entry point
Routes API Gateway requests to the appropriate handler.
Validates input, writes PENDING records to DynamoDB.
DynamoDB Streams → SQS → Provisioning service handles the rest.
"""
import json
import logging

from src.handlers import spaces, access, notifications
from src.utils.response import ok, bad_request, not_found, server_error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ROUTES = {
    ("POST", "/spaces"):        spaces.handle_create,
    ("POST", "/access"):        access.handle_create,
    ("POST", "/notifications"): notifications.handle_create,
}


def handler(event, context):
    logger.info("Event: %s", json.dumps(event))

    method = event.get("httpMethod", "")
    path   = event.get("path", "")

    route_handler = ROUTES.get((method, path))

    if not route_handler:
        return not_found(f"Route {method} {path} not found")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    try:
        return route_handler(body)
    except ValueError as e:
        return bad_request(str(e))
    except Exception as e:
        logger.exception("Unhandled error")
        return server_error(str(e))
