from typing import Any

from netlist_carpentry.utils.log import initialize_logging


def pytest_configure(config: Any) -> None:
    initialize_logging(no_file=True)
    from netlist_carpentry import CFG

    CFG.allow_detached_segments = True
