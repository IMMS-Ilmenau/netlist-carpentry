import logging
import os
from pathlib import Path
from typing import Any

from netlist_carpentry.utils.log import initialize_logging


def pytest_configure(config: Any) -> None:
    initialize_logging()
    from netlist_carpentry import CFG

    CFG.allow_detached_segments = True


def pytest_runtest_setup(item: object) -> None:
    """Disable logging before a doctest runs."""
    # Checks if the test item is a Doctest module (.py) or Doctest textfile (.rst/.md)
    if 'Doctest' in item.__class__.__name__:
        logging.disable(logging.CRITICAL)


def pytest_runtest_teardown(item: object) -> None:
    """Re-enable logging after the doctest finishes."""
    if 'Doctest' in item.__class__.__name__:
        logging.disable(logging.NOTSET)


nc_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
collect_ignore = [
    nc_dir / 'src' / 'netlist_carpentry' / 'io' / 'read' / 'yosys_netlist.py',
    nc_dir / 'src' / 'netlist_carpentry' / 'io' / 'read' / 'yosys_netlist_types.py',
]
