"""
Utility functions used in the transpilation process.
"""


def hyphenate(text: str):
    """
    Converts underscores to hyphens since Python functions use underscores
    whilst we tend to use hyphens for Argo template names.
    """
    return text.replace("_", "-")
