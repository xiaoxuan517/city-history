from __future__ import annotations

import argparse
import subprocess
import sys

API_APP = "app.api.main:app"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified project entrypoint.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    web_parser = subparsers.add_parser("web", help="Start the FastAPI web UI and API.")
    web_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="FastAPI server host.",
    )
    web_parser.add_argument(
        "--port",
        default="8000",
        help="FastAPI server port.",
    )
    web_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn reload for local development.",
    )

    return parser


def _run_web(*, host: str, port: str, reload: bool) -> int:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        API_APP,
        "--host",
        host,
        "--port",
        port,
    ]
    if reload:
        command.append("--reload")
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "web":
        return _run_web(
            host=args.host,
            port=args.port,
            reload=args.reload,
        )

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
