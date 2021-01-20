"""
Definitions of paths that are often used to e.g. import data.
"""

from pathlib import Path


PKG_ROOT_DIR = Path(__file__).resolve().parents[1]
PKG_DATA_DIR = PKG_ROOT_DIR / "data"
