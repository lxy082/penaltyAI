# config.py
from __future__ import annotations
from pathlib import Path

DIRS = ["L", "C", "R"]

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "penalties.csv"
