import functools
import json
import logging
from collections.abc import Callable
from typing import Any

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

auth_blueprint = Blueprint("auth", __name__)


def _load_users(users_file: str) -> dict[str, str | None]:
    try:
        with open(users_file) as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Users file not found: {users_file}")
        return {}
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in users file: {users_file}")
        return {}


def _save_users(users_file: str, users: dict[str, str | None]) -> None:
    with open(users_file, "w") as f:
        json.dump(users, f, indent=2)
        f.write("\n")


def login_required(f: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated


@auth_blueprint.route("/login", methods=["GET"])
def login() -> str:
    if "username" in session:
        return redirect(url_for("stats.dashboard"))
    return render_template("login.html")


@auth_blueprint.route("/login", methods=["POST"])
def login_post() -> str:
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    users = _load_users(current_app.config["USERS_FILE"])

    if username not in users:
        return render_template("login.html", error="Invalid username or password")

    password_hash = users[username]

    if password_hash is None:
        session["pending_password_setup"] = username
        return redirect(url_for("auth.set_password"))

    if check_password_hash(password_hash, password):
        session["username"] = username
        return redirect(url_for("stats.dashboard"))

    return render_template("login.html", error="Invalid username or password")


@auth_blueprint.route("/set-password", methods=["GET"])
def set_password() -> str:
    if "pending_password_setup" not in session:
        return redirect(url_for("auth.login"))
    return render_template("set_password.html", username=session["pending_password_setup"])


@auth_blueprint.route("/set-password", methods=["POST"])
def set_password_post() -> str:
    if "pending_password_setup" not in session:
        return redirect(url_for("auth.login"))

    username = session["pending_password_setup"]
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")

    if not password:
        return render_template("set_password.html", username=username, error="Password cannot be empty")

    if password != confirm:
        return render_template("set_password.html", username=username, error="Passwords do not match")

    users_file = current_app.config["USERS_FILE"]
    users = _load_users(users_file)
    users[username] = generate_password_hash(password)
    _save_users(users_file, users)

    session.pop("pending_password_setup", None)
    session["username"] = username
    return redirect(url_for("stats.dashboard"))


@auth_blueprint.route("/logout", methods=["POST"])
def logout() -> str:
    session.clear()
    return redirect(url_for("auth.login"))
