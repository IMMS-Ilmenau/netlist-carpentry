"""Package for reading VCD files, analyzing simulation data and extracting heuristics from them."""

from .parsing import (
    apply_vcd_data,
    equal_toggles,
    filter_signals,
    filter_signals_per_scope,
    find_matching_signals,
    get_hierarchy_dict,
    map_names_to_circuit,
)
from .wrapper import VCDScope, VCDVar, VCDWaveform

__all__ = [
    'VCDScope',
    'VCDVar',
    'VCDWaveform',
    'apply_vcd_data',
    'equal_toggles',
    'filter_signals',
    'filter_signals_per_scope',
    'find_matching_signals',
    'get_hierarchy_dict',
    'map_names_to_circuit',
]
