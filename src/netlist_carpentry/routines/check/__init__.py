"""A package to handle circuit checks that do not change the behaviour or structure, but analyze the circuit in certain aspects."""

from .comb_loops import find_comb_loops, has_comb_loops
from .fanout_analysis import fanout

__all__ = ['fanout', 'find_comb_loops', 'has_comb_loops']
