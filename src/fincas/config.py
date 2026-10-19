from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Carpeta del proyecto (config.yaml, data/, state/): la actual, o FINCAS_ROOT
ROOT = Path(os.environ.get("FINCAS_ROOT") or Path.cwd()).resolve()
DATA_DIR = ROOT / "data"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
