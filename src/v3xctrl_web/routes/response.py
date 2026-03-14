from typing import Any

from flask import Response, jsonify


def success(data: Any = None, status: int = 200) -> tuple[Response, int]:
    return jsonify({"data": data, "error": None}), status


def error(message: str, details: str | None = None, status: int = 500) -> tuple[Response, int]:
    return jsonify({"data": None, "error": {"message": message, "details": details}}), status
