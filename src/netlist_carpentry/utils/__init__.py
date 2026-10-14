"""Miscellaneous stuff and utilities."""

from typing import Iterable, Optional

from tqdm import tqdm

from .cfg import CFG
from .log import LOG, initialize_logging
from .verilog import VERILOG_KEYWORDS

__all__ = ['CFG', 'LOG', 'VERILOG_KEYWORDS', 'initialize_logging']


def progress_bar(iterable: Iterable, desc: Optional[str] = None) -> tqdm:
    """A tqdm-based progress bar, customized for usage within Netlist Carpentry.

    Args:
        iterable (Iterable): The iterable for which the progress bar should be shown
        desc (Optional[str], optional): An optional progress bar description. Defaults to None.

    Returns:
        tqdm: The tqdm element based on the given iterable handling the progress bar.
    """
    from netlist_carpentry import CFG

    return tqdm(iterable, desc=desc, leave=False, disable=CFG.disable_tqdm)
