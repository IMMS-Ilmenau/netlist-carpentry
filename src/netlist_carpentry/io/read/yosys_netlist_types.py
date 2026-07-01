import sys
import warnings

from .yosys import netlist_types

new_path = 'netlist_carpentry.io.read.yosys.netlist_types'
warnings.warn(
    f'Importing {__name__!r} is deprecated and will be removed in v1.0.0. '
    f'This module has been renamed and moved to {new_path!r}! '
    f"Please use 'import {new_path}' instead.",
    DeprecationWarning,
    stacklevel=2,
)

sys.modules[__name__] = netlist_types
