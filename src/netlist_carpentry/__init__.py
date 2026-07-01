# ruff: noqa: E402 # Module imports are not at top because of required constants
# isort: skip_file
import os
import platform
import shutil

try:
    import pywellen  # noqa: F401

    HAS_VCD = True
except ImportError:
    HAS_VCD = False


NC_DIR = os.path.dirname(os.path.abspath(__file__))
"""The root directory of Netlist Carpentry."""
ON_WINDOWS = 'win' in platform.system().lower()
"""Whether Netlist Carpentry is running on Windows."""


from netlist_carpentry.utils import CFG, LOG, initialize_logging, VERILOG_KEYWORDS  # Config and log must be loaded before the other modules
from netlist_carpentry.core.graph import EMPTY_GRAPH
from netlist_carpentry.core.enums import Direction, Signal
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import (
    WIRE_SEGMENT_0,
    WIRE_SEGMENT_1,
    WIRE_SEGMENT_X,
    WIRE_SEGMENT_Z,
    CONST_MAP_VAL2OBJ,
    CONST_MAP_VAL2VERILOG,
    CONST_MAP_YOSYS2OBJ,
    WireSegment,
)
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.utils import gate_factory, gate_lib
from netlist_carpentry.io.read.yosys import ReadConfig
from netlist_carpentry.io.read.read_utils import read_json, read, read_via_cfg, generate_json
from netlist_carpentry.io.write.write_utils import write
from netlist_carpentry.core.graph.pattern import EMPTY_PATTERN
from netlist_carpentry.scripts import NC_SCRIPTS_DIR, run_equiv, run_eqy, run_equiv_miter
from netlist_carpentry.core.graph import ModuleGraph

Port.model_rebuild()
Wire.model_rebuild()
Instance.model_rebuild()
Module.model_rebuild()

__all__ = [
    'CFG',
    'CONST_MAP_VAL2OBJ',
    'CONST_MAP_VAL2VERILOG',
    'CONST_MAP_YOSYS2OBJ',
    'EMPTY_GRAPH',
    'EMPTY_PATTERN',
    'LOG',
    'NC_DIR',
    'NC_SCRIPTS_DIR',
    'VERILOG_KEYWORDS',
    'WIRE_SEGMENT_0',
    'WIRE_SEGMENT_1',
    'WIRE_SEGMENT_X',
    'WIRE_SEGMENT_Z',
    'Circuit',
    'Direction',
    'Instance',
    'Module',
    'ModuleGraph',
    'NetlistElement',
    'Port',
    'PortSegment',
    'ReadConfig',
    'Signal',
    'Wire',
    'WireSegment',
    'gate_factory',
    'gate_lib',
    'generate_json',
    'read',
    'read_json',
    'read_via_cfg',
    'run_equiv',
    'run_equiv_miter',
    'run_eqy',
    'write',
]


# Activate rudimentary LOG handling at first import
if not LOG._init_finished:
    initialize_logging()

yosys_path = shutil.which('yosys')
if not yosys_path:
    CFG.yosys_executable = 'yowasp-yosys'
    LOG.warn("Unable to locate default Yosys command 'yosys'. Falling back to 'yowasp-yosys'!")
