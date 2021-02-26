"""
Definitions of paths that are often used to e.g. import data.
"""
import os
from pathlib import Path


PKG_ROOT_DIR = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = PKG_ROOT_DIR / "examples"
EXAMPLES_DATA = EXAMPLES_DIR / "data" / "testing" / "scargo-examples"


def env_local_mountpoint() -> Path:
    """
    Get local mount point as defined by the environment variable SCARGO_LOCAL_MOUNT.
    """
    local_mountpoint = os.getenv("SCARGO_LOCAL_MOUNT")

    if local_mountpoint is None:
        raise ValueError("Environment variable SCARGO_LOCAL_MOUNT not defined.")

    local_mountpoint = Path(local_mountpoint)
    if not local_mountpoint.is_dir():
        raise ValueError(f"Cannot find directory SCARGO_LOCAL_MOUNT={local_mountpoint}")
    else:
        return local_mountpoint
