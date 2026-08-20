import json
from pathlib import Path

from config.settings import INGEST_MANIFEST_PATH, INGEST_PIPELINE_VERSION


def load_manifest() -> dict:
    path = Path(INGEST_MANIFEST_PATH)
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("_version") != INGEST_PIPELINE_VERSION:
        return {}

    return data.get("sources", {})


def save_manifest(manifest: dict):
    path = Path(INGEST_MANIFEST_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "_version": INGEST_PIPELINE_VERSION,
        "sources": manifest,
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def diff_sources(current: dict[str, dict], previous: dict) -> tuple[list[str], list[str]]:
    changed = [
        source
        for source, fingerprint in current.items()
        if previous.get(source) != fingerprint
    ]
    deleted = [source for source in previous if source not in current]

    return changed, deleted
