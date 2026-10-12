import hashlib
import json
import zipfile
from pathlib import Path
from supportpilot.generation import PROMPT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def main():
    if PROMPT_VERSION != "answerability-2.3":
        raise RuntimeError("Capture expects the verified v2.3 baseline")
    destination = ROOT / "releases"
    destination.mkdir(exist_ok=True)
    target = destination / "supportpilot-v2.3-code.zip"
    if target.exists():
        raise RuntimeError("Snapshot already exists; preserve it")
    files = []
    for folder in ["supportpilot", "scripts", "tests", "docs", "data", "reports/baselines"]:
        files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    files.extend(ROOT / name for name in ["README.md", "pyproject.toml", "requirements.lock.txt", ".gitignore"] if (ROOT / name).exists())
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in hashes:
            archive.write(ROOT / relative, relative)
    manifest = {"prompt_version": PROMPT_VERSION, "archive_sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "files": hashes, "limitations": "Code snapshot only. WSL pip freeze, model revision and actual runtime metadata must be captured separately. Excludes customer SQLite history."}
    target.with_suffix(".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
