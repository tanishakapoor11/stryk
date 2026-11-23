"""Download and extract a Cricsheet JSON dataset into data/raw/<name>/.

Usage: python scripts/fetch_cricsheet.py [dataset]   (default: ipl)

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

DATASETS = {
    "ipl": "https://cricsheet.org/downloads/ipl_json.zip",
    "t20s": "https://cricsheet.org/downloads/t20s_json.zip",
    "odis": "https://cricsheet.org/downloads/odis_json.zip",
    "tests": "https://cricsheet.org/downloads/tests_json.zip",
}
ROOT = Path(__file__).resolve().parents[1]


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
