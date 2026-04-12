from __future__ import annotations

import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import dotenv_values


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_ENV = BACKEND_DIR / ".env"
FRONTEND_ENV = FRONTEND_DIR / ".env"
BACKEND_READY_URL = "http://localhost:8000/ready"
FRONTEND_URL = "http://localhost:5173"


def check_file(path: Path, hint: str) -> None:
    if not path.exists():
        raise SystemExit(f"Missing {path}. {hint}")


def check_command(name: str, hint: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Missing command `{name}`. {hint}")


def has_command(name: str) -> bool:
    return shutil.which(name) is not None


def wait_for_url(url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
        except URLError as exc:
            last_error = str(exc)
        time.sleep(1)
    raise SystemExit(f"Timed out waiting for {url}. Last error: {last_error}")


def load_env(path: Path) -> dict[str, str]:
    values = dotenv_values(path)
    return {key: str(value) for key, value in values.items() if value is not None}


def preflight() -> tuple[dict[str, str], dict[str, str], bool]:
    check_file(BACKEND_ENV, "Copy backend/.env.example to backend/.env first.")
    check_file(FRONTEND_ENV, "Copy frontend/.env.example to frontend/.env first.")
    frontend_enabled = has_command("npm")

    backend_env = load_env(BACKEND_ENV)
    frontend_env = load_env(FRONTEND_ENV)

    llm_model_path = (BACKEND_DIR / backend_env.get("LLM_MODEL_PATH", "../models/Qwen3-4B-Q4_K_M.gguf")).resolve()
    embedding_model_path = (BACKEND_DIR / backend_env.get("EMBEDDING_MODEL", "../models/bge-m3")).resolve()
    reranker_model_path = (BACKEND_DIR / backend_env.get("RERANKER_MODEL", "../models/bge-reranker-base")).resolve()

    check_file(llm_model_path, "Add your GGUF model to models/ and update LLM_MODEL_PATH if needed.")
    check_file(embedding_model_path / "config.json", "bge-m3 is missing or incomplete.")
    if backend_env.get("RERANKER_ENABLED", "true").lower() == "true":
        check_file(reranker_model_path / "config.json", "bge-reranker-base is missing or incomplete.")

    return backend_env, frontend_env, frontend_enabled


def launch_process(command: list[str], cwd: Path) -> subprocess.Popen:
    return subprocess.Popen(command, cwd=cwd, start_new_session=True)


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> None:
    backend_process: subprocess.Popen | None = None
    frontend_process: subprocess.Popen | None = None

    try:
        _, _, frontend_enabled = preflight()
        backend_process = launch_process(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
            BACKEND_DIR,
        )
        print("Starting backend...")
        wait_for_url(BACKEND_READY_URL, timeout_seconds=60)
        print(f"Backend ready: {BACKEND_READY_URL}")

        if frontend_enabled:
            frontend_process = launch_process(["npm", "run", "dev"], FRONTEND_DIR)
            print("Starting frontend...")
            wait_for_url(FRONTEND_URL, timeout_seconds=60)
            print(f"Frontend ready: {FRONTEND_URL}")
        else:
            print("npm was not found, so frontend startup was skipped.")
            print("Install Node.js 20+ to run the React frontend.")
        print("Press Ctrl+C to stop running services.")

        while True:
            if backend_process.poll() is not None:
                raise SystemExit(f"Backend exited with code {backend_process.returncode}")
            if frontend_process is not None and frontend_process.poll() is not None:
                raise SystemExit(f"Frontend exited with code {frontend_process.returncode}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        stop_process(frontend_process)
        stop_process(backend_process)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.default_int_handler)
    main()
