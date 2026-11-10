import argparse
import logging
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

SERVICE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = SERVICE_DIR / ".env"
DEFAULT_MODELS_DIR = SERVICE_DIR / "models"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def parse_env(env_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not env_path.is_file():
        return env

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip().strip("\"'")
    return env


def parse_url(url: str, default_port: int) -> tuple[str, int]:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return parsed.hostname or "127.0.0.1", parsed.port or default_port


def resolve_model(name: str, models_dir: Path) -> Path:
    for candidate in (Path(name), models_dir / name, models_dir / f"{name}.gguf"):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError


def build_commands(env: dict[str, str], models_dir: Path) -> list[tuple[str, list[str]]]:
    ctx = env.get("LLM_CONTEXT_WINDOW", "8000")
    specs = [
        ("LLM", "LLM_MODEL", "LLM_URL", 8080, ["-c", ctx]),
        ("Embedding", "EMB_MODEL", "EMB_URL", 8081, ["--embedding"]),
        ("Reranker", "RRK_MODEL", "RRK_URL", 8082, ["--reranking"]),
    ]

    commands: list[tuple[str, list[str]]] = []
    for name, model_key, url_key, default_port, extra_args in specs:
        model = env.get(model_key, "")
        if not model:
            logger.warning(f"Model {name} not found")
            continue
        model_path = resolve_model(model, models_dir)
        host, port = parse_url(env.get(url_key, ""), default_port)
        cmd = [
            "llama-server",
            "-m",
            str(model_path),
            "--host",
            host,
            "--port",
            str(port),
            *extra_args,
        ]
        commands.append((name, cmd))

    return commands


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    args = parser.parse_args()

    env = parse_env(args.env_file)
    commands = build_commands(env, args.models_dir)
    if not commands:
        logger.error("No models found in .env")
        return

    processes: list[tuple[str, subprocess.Popen]] = []
    try:
        for name, cmd in commands:
            logger.info(f"Starting {name} with command: {' '.join(cmd)}")
            processes.append((name, subprocess.Popen(cmd)))

        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    raise RuntimeError(f"{name} server has error")
            time.sleep(1.0)
    except (KeyboardInterrupt, RuntimeError) as e:
        if isinstance(e, RuntimeError):
            logger.error(f"{e}")
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                logger.info(f"Stopping {name}")
                proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    main()
