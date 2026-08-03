"""
HTTP response helpers for API Gateway Lambda proxy integration.
"""
import json


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def ok(body: dict) -> dict:
    return _response(200, body)


def created(body: dict) -> dict:
    return _response(202, body)


def bad_request(message: str) -> dict:
    return _response(400, {"error": message})


def not_found(message: str) -> dict:
    return _response(404, {"error": message})


def server_error(message: str) -> dict:
    return _response(500, {"error": message})
