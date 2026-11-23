"""Download and extract a Cricsheet JSON dataset into data/raw/<name>/.

Usage: python scripts/fetch_cricsheet.py [dataset]   (default: ipl; any key in
backend/app/catalog/sources.json, e.g. wpl, bbl, t20s)

Cricsheet publishes one zip of per-match JSON files per competition.
Downloaded archives are untrusted input: each dataset is extracted into its
own directory and member paths are validated before writing.
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

import json

ROOT = Path(__file__).resolve().parents[1]
# Every dataset Cricsheet publishes, from the source registry, so a new
# competition needs a catalogue entry rather than an edit here.
_SOURCES = json.loads((ROOT / "backend" / "app" / "catalog" / "sources.json").read_text())
DATASETS = {
    d["key"]: d["url"]
    for s in _SOURCES["sources"] if s["slug"] == "cricsheet"
    for d in s["datasets"]
}


def fetch(name: str) -> Path:
    if name not in DATASETS:
        raise SystemExit(f"unknown dataset {name!r}; choose from {sorted(DATASETS)}")
    dest = ROOT / "data" / "raw" / f"{name}_json"
    dest.mkdir(parents=True, exist_ok=True)
    url = DATASETS[name]
    print(f"downloading {url}")
    with urlopen(url, timeout=120) as resp:  # noqa: S310 - fixed https host
        blob = resp.read()
    print(f"  {len(blob) / 1e6:.1f} MB; extracting to {dest}")
    written = 0
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target = (dest / member.filename).resolve()
            if dest.resolve() not in target.parents:
                print(f"  skipping suspicious member {member.filename!r}")
                continue
            if not member.filename.endswith((".json", ".txt")):
                continue
            target.write_bytes(zf.read(member))
            written += 1
    print(f"  wrote {written} files")
    return dest


if __name__ == "__main__":
    fetch(sys.argv[1] if len(sys.argv) > 1 else "ipl")
