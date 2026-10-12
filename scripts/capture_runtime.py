import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", choices=["api", "vllm"], required=True)
    args = parser.parse_args()
    packages = {package.metadata["Name"]: package.version for package in importlib.metadata.distributions() if package.metadata.get("Name")}
    data = {"label": args.label, "python": sys.version, "platform": platform.platform(), "packages": packages, "settings": {key: os.getenv(key) for key in ["SUPPORTPILOT_RETRIEVAL", "SUPPORTPILOT_MODEL", "SUPPORTPILOT_WARMUP", "SUPPORTPILOT_BM25_THRESHOLD", "SUPPORTPILOT_DENSE_THRESHOLD", "VLLM_USE_FLASHINFER_SAMPLER"]}}
    try:
        data["gpu"] = subprocess.check_output(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], text=True, timeout=10).strip()
    except (OSError, subprocess.SubprocessError):
        data["gpu"] = None
    try:
        from huggingface_hub import try_to_load_from_cache
        config = try_to_load_from_cache("Qwen/Qwen3-4B-Instruct-2507", "config.json")
        data["cached_model_revision"] = Path(config).parent.name if isinstance(config, str) else None
    except ImportError:
        data["cached_model_revision"] = None
    # A cached snapshot is not proof that the running server loaded that revision.
    data["limitations"] = "Capture current environment, not past benchmark environment. Cached model revision must be checked against running server options. GPU startup arguments are in scripts/start_vllm.sh."
    directory = ROOT / "reports/environments"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{args.label}-{time.time_ns()}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
