"""Start the Gyminators development site with one Python command.

Usage:
    python run.py
    python run.py --port 8080 --no-browser
    python run.py --use-environment-database

This launcher is intentionally for local development. Production is started by
Gunicorn through the Docker Compose configuration.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
MANAGE_PY = PROJECT_ROOT / "manage.py"


def run_manage(*arguments: str) -> None:
    """Run a Django management command and stop on failure."""
    subprocess.run(
        [sys.executable, str(MANAGE_PY), *arguments],
        cwd=PROJECT_ROOT,
        check=True,
        env=os.environ.copy(),
    )


def open_when_ready(host: str, port: int) -> None:
    """Open the browser once Django accepts connections."""
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((browser_host, port), timeout=0.5):
                webbrowser.open(f"http://{browser_host}:{port}/")
                return
        except OSError:
            time.sleep(0.25)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Gyminators locally.")
    parser.add_argument("--host", default="127.0.0.1", help="Listening host (default: 127.0.0.1).")
    parser.add_argument("--port", default=8000, type=int, help="Listening port (default: 8000).")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the site automatically.")
    parser.add_argument("--skip-migrate", action="store_true", help="Skip database migrations and role setup.")
    parser.add_argument("--create-admin", action="store_true", help="Open Django's interactive administrator setup before starting.")
    parser.add_argument(
        "--use-environment-database",
        action="store_true",
        help="Use DB_HOST and related environment settings instead of local SQLite.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gyminators.settings")
    # This file is a local-development convenience, even if the calling shell
    # still has production-flavoured variables from another session.
    os.environ["DJANGO_DEBUG"] = "true"
    os.environ["ALLOWED_HOSTS"] = (
        "*" if args.host in {"0.0.0.0", "::"} else f"{args.host},localhost,127.0.0.1,[::1]"
    )
    if not args.use_environment_database:
        # A one-click local preview must never inherit production database
        # credentials from a previously configured terminal session.
        for name in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"):
            os.environ.pop(name, None)

    try:
        import django  # noqa: F401
    except ImportError:
        print(
            "Django is not installed. Run `python -m pip install -r requirements.txt` "
            "once, then run `python run.py` again.",
            file=sys.stderr,
        )
        return 1

    try:
        if not args.skip_migrate:
            print("Preparing the local database...")
            run_manage("migrate")
            run_manage("setup_roles")
        if args.create_admin:
            run_manage("createsuperuser")
    except subprocess.CalledProcessError as exc:
        print(f"Setup stopped because a management command failed (exit {exc.returncode}).", file=sys.stderr)
        return exc.returncode

    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(args.host, args.port), daemon=True).start()

    print(f"Starting Gyminators at http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop the development server.")
    try:
        return subprocess.call(
            [sys.executable, str(MANAGE_PY), "runserver", f"{args.host}:{args.port}"],
            cwd=PROJECT_ROOT,
            env=os.environ.copy(),
        )
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
