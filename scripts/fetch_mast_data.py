#!/usr/bin/env python3
"""Fetch the MAST human-labeled dataset into ./data/ (git-ignored).

The dataset is public research data from Cemri et al., "Why Do Multi-Agent LLM
Systems Fail?" (arXiv:2503.13657). We keep it out of git (2.6 MB, not ours to
redistribute) and download on demand.

Usage:
    python scripts/fetch_mast_data.py            # human-labeled subset (19 traces)
    python scripts/fetch_mast_data.py --full     # full LLM+human dataset (~1600 traces)
"""
from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/datasets/mcemri/MAD/resolve/main"
FILES = {
    "human": "MAD_human_labelled_dataset.json",
    "full": "MAD_full_dataset.json",
}
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def fetch(which: str) -> Path:
    name = FILES[which]
    DATA_DIR.mkdir(exist_ok=True)
    dest = DATA_DIR / name
    url = f"{BASE}/{name}"
    print(f"downloading {url}\n        -> {dest}")
    urllib.request.urlretrieve(url, dest)  # noqa: S310 — fixed, trusted HTTPS host
    print(f"done: {dest.stat().st_size:,} bytes")
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--full", action="store_true", help="fetch the full dataset instead of the human subset")
    args = ap.parse_args()
    fetch("full" if args.full else "human")


if __name__ == "__main__":
    main()
