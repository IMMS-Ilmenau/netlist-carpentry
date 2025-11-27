"""Custom dictionary, only used for string formatting via `str.format_map` that allows missing entries."""

from typing import Dict


class SafeFormatDict(Dict[str, str]):
    """Simple Dictionary class used for str.format_map to ignore unset placeholders instead of raising an error."""

    def __missing__(self, key: str) -> str:
        # Leave unknown placeholders untouched
        return '{' + key + '}'
