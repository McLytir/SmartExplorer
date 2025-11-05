from __future__ import annotations

import argparse
import atexit
import os
import subprocess
import sys
import time
from typing import Optional


def _is_server_up(url: str) -> bool:
    try:
        import httpx
        with httpx.Client(timeout=2.0) as c:
            r = c.get(url.rstrip('/') + "/api/settings")
            return r.status_code == 200
    except Exception:
        return False


def _start_server(python: str, host: str = "127.0.0.1", port: int = 5001) -> Optional[subprocess.Popen]:
    # If a server already responds, don't start another
    base = f"http://{host}:{port}"
    if _is_server_up(base):
        return None

    env = os.environ.copy()
    proc = subprocess.Popen([python, "-m", "smart_explorer.backend.server"], env=env)

    # Wait briefly until it responds (max ~10s)
    for _ in range(50):
        if _is_server_up(base):
            break
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    return proc


def _run_app_subprocess(env: dict | None = None) -> int:
    """Launch the Qt UI in a separate process so server and UI don't interfere."""
    try:
        proc = subprocess.Popen([sys.executable, "-m", "smart_explorer.app"], env=env)
    except Exception:
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass
        return 1
    try:
        return proc.wait()
    except KeyboardInterrupt:
        try:
            proc.terminate()
        except Exception:
            pass
        return 130


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m smart_explorer", description="Run SmartExplorer UI and/or backend server")
    parser.add_argument("--mode", choices=["both", "server", "app"], default="both", help="What to run")
    parser.add_argument("--host", default="127.0.0.1", help="Backend host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5001, help="Backend port (default: 5001)")
    args = parser.parse_args(argv)

    server_proc: Optional[subprocess.Popen] = None
    exit_code = 0

    try:
        if args.mode in ("both", "server"):
            server_proc = _start_server(sys.executable, host=args.host, port=args.port)
            if server_proc is not None:
                atexit.register(lambda: server_proc.poll() is None and server_proc.terminate())

        if args.mode in ("both", "app"):
            env = os.environ.copy()
            env.setdefault("SMX_BACKEND_URL", f"http://{args.host}:{args.port}")
            exit_code = _run_app_subprocess(env)
        else:
            try:
                while True:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                exit_code = 0
    finally:
        if server_proc is not None and server_proc.poll() is None:
            try:
                server_proc.terminate()
            except Exception:
                pass

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
