"""Fetch the two large published logs at an immutable commit and verify exact bytes."""

import json
import urllib.request
from pathlib import Path

from .io import sha256_file


def fetch_upstream(destination="data/upstream"):
    destination = Path(destination)
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    commit = manifest["commit"]
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("Expected a pinned Git commit SHA")
    fetched = []
    for name in ("results.jsonl", "results_sweep.jsonl"):
        meta = manifest["files"][name]
        target = destination / name
        if target.exists():
            if sha256_file(target) != meta["sha256"]:
                raise ValueError(f"Existing {name} has the wrong hash; investigate before replacing")
            fetched.append({"file": name, "status": "already_verified"})
            continue
        url = f"https://raw.githubusercontent.com/twospoon/READ/{commit}/results/{name}"
        with urllib.request.urlopen(url, timeout=45) as response:
            data = response.read(meta["bytes"] + 1)
        if len(data) != meta["bytes"]:
            raise ValueError(f"Unexpected download size: {name}")
        import hashlib
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ValueError(f"Downloaded hash mismatch: {name}")
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_bytes(data)
        temp.replace(target)
        fetched.append({"file": name, "status": "downloaded_verified"})
    return fetched
