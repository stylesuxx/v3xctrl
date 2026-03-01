from flask import jsonify
from typing import Any, Tuple

from flask import Response


def success(data: Any = None, status: int = 200) -> Tuple[Response, int]:
    return jsonify({"data": data, "error": None}), status


def error(message: str, details: str | None = None, status: int = 500) -> Tuple[Response, int]:
    return jsonify({"data": None, "error": {"message": message, "details": details}}), status
