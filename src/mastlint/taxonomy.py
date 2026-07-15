"""Load and expose the MAST taxonomy from taxonomy/taxonomy.yaml.

The YAML is the single source of truth for the 14 failure modes. Code and judge
prompts both read from it so that sharpening a definition updates the whole tool.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import yaml

# repo-root/taxonomy/taxonomy.yaml  (…/src/mastlint/taxonomy.py -> parents[2])
TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "taxonomy" / "taxonomy.yaml"


@dataclass(frozen=True)
class FailureMode:
    id: str
    name: str
    category: str
    operational_definition: str
    signals: list[str]
    positive_example: str
    near_miss: str
    confused_with: list[str]


@lru_cache(maxsize=1)
def load_taxonomy(path: Path | None = None) -> dict:
    with open(path or TAXONOMY_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=1)
def failure_modes() -> list[FailureMode]:
    data = load_taxonomy()
    return [
        FailureMode(
            id=fm["id"],
            name=fm["name"],
            category=fm["category"],
            operational_definition=fm["operational_definition"].strip(),
            signals=fm.get("signals", []),
            positive_example=fm.get("positive_example", "").strip(),
            near_miss=fm.get("near_miss", "").strip(),
            confused_with=fm.get("confused_with", []),
        )
        for fm in data["failure_modes"]
    ]
