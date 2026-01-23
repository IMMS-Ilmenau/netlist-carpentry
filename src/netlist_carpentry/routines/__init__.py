"""Some pre-defined routines, which might be helpful."""

from .check import fanout, find_comb_loops, has_comb_loops
from .opt import clean_circuit, opt_constant, opt_driverless, opt_loadless

__all__ = ['clean_circuit', 'fanout', 'find_comb_loops', 'has_comb_loops', 'opt_constant', 'opt_driverless', 'opt_loadless']
