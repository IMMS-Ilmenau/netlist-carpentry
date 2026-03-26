"""Script that may be used in certain use cases, mainly dynamically generated."""

import os

from .equivalence_checking import run_equiv, run_equiv_miter, run_eqy

NC_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

__all__ = ['NC_SCRIPTS_DIR', 'run_equiv', 'run_equiv_miter', 'run_eqy']
