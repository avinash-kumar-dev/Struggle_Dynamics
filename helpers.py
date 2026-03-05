"""
Helper utilities for the Struggle Dynamics module.
"""
import json
import os
from pathlib import Path


def save_to_json(data: dict, filepath: str, indent: int = 2) -> None:
    """Save data to a JSON file, creating parent directories as needed."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
