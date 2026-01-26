"""Miscellaneous stuff and utilities."""

from .cfg import CFG
from .log import LOG, initialize_logging
from .verilog import VERILOG_KEYWORDS

__all__ = ['CFG', 'LOG', 'VERILOG_KEYWORDS', 'initialize_logging']
