"""Package to handle input and output of circuit data, i.e. transformation from text files to the internal representation, and back."""

from netlist_carpentry import HAS_VCD

if HAS_VCD:
    from .vcd import VCDWaveform, equal_toggles, filter_signals, filter_signals_per_scope, map_names_to_circuit

__all__ = ['VCDWaveform', 'equal_toggles', 'filter_signals', 'filter_signals_per_scope', 'map_names_to_circuit']
