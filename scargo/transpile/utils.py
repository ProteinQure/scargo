"""
Utility functions used in the transpilation process.
"""

from typing import Dict, NamedTuple, Optional


def hyphenate(text: str):
    """
    Converts underscores to hyphens since Python functions use underscores
    whilst we tend to use hyphens for Argo template names.
    """
    return text.replace("_", "-")


class Transput(NamedTuple):
    """
    Transput is the hypernym of inputs & outputs. This named tuple provides
    convenient access to the input (or output) parameters and artifacts of a
    WorkflowStep.
    """

    parameters: Optional[Dict] = None
    artifacts: Optional[Dict] = None
