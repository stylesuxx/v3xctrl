import subprocess

try:
    from v3xctrl_ui._version import VERSION
    __version__ = VERSION
except ImportError:
    # Local development: resolve hash from git
    try:
        _hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL
        ).decode().strip()
        __version__ = f"development build, {_hash}"
    except Exception:
        __version__ = "development build"
