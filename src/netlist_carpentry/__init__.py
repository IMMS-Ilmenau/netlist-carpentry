# isort: skip_file
import os
import shutil

from netlist_carpentry.utils.cfg import CFG  # Config and log must be loaded before the other modules
from netlist_carpentry.utils.log import Log, LOG, initialize_logging
from netlist_carpentry.core.graph import EMPTY_GRAPH
from netlist_carpentry.core.netlist_elements.wire_segment import (
    WIRE_SEGMENT_0,
    WIRE_SEGMENT_1,
    WIRE_SEGMENT_X,
    WIRE_SEGMENT_Z,
    CONST_MAP_VAL2OBJ,
    CONST_MAP_VAL2VERILOG,
    CONST_MAP_YOSYS2OBJ,
)
from netlist_carpentry.core.graph.pattern import EMPTY_PATTERN
from netlist_carpentry.scripts import NC_SCRIPTS_DIR
from netlist_carpentry.api.read.read_utils import read_json, read
from netlist_carpentry.api.write.write_utils import write
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.utils import gate_lib, gate_lib_factory

Port.model_rebuild()

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
    'WIRE_SEGMENT_0',
    'WIRE_SEGMENT_1',
    'WIRE_SEGMENT_X',
    'WIRE_SEGMENT_Z',
    'Circuit',
    'Instance',
    'Module',
    'Port',
    'Wire',
    'gate_lib',
    'gate_lib_factory',
    'read',
    'read_json',
    'write',
]

NC_DIR = os.path.dirname(os.path.abspath(__file__))

# Activate rudimentary LOG handling at first import
if not Log._init_finished:
    initialize_logging(no_file=True)

yosys_path = shutil.which('yosys')
if not yosys_path:
    LOG.warn(
        'Unable to locate Yosys. Install Yosys, if it is not already installed. '
        + 'Otherwise, check your Path variable, and whether Yosys can be executed via the command "yosys".'
    )
