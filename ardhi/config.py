"""Centralized filesystem and database path configuration for the project."""
from pathlib import Path
import os


ROOT_DIR = Path(__file__).resolve().parents[1]

HWSD_DB_PATH = os.getenv("HWSD_DB_PATH", str(ROOT_DIR / "hwsd.db"))
ARDHI_DB_PATH = os.getenv("ARDHI_DB_PATH", str(ROOT_DIR / "ardhi.db"))
ECOCROP_DB_PATH = os.getenv("ECOCROP_DB_PATH", str(ROOT_DIR / "ecocrop.db"))
