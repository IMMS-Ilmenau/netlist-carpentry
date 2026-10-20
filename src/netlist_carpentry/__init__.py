# ruff: noqa: E402, RUF100 # Module imports are not at top because of required constants
# isort: skip_file
import os
import platform
import shutil


try:
    import pywellen  # noqa: F401

    HAS_VCD = True
except ImportError:
    HAS_VCD = False


def _nc_version() -> str:
    from importlib.metadata import version, PackageNotFoundError

    try:
        return version('netlist-carpentry')
    except PackageNotFoundError:
        # This happens if the package isn't installed (e.g., just copied the files)
        return 'unknown'


__version__ = _nc_version()

NC_DIR = os.path.dirname(os.path.abspath(__file__))
"""The root directory of Netlist Carpentry."""
# Older windows Versions have 'win32', newer ones have 'Windows', hence this rather weird check
ON_WINDOWS = 'win' in platform.system().lower() and 'darwin' not in platform.system().lower()
"""Whether Netlist Carpentry is running on Windows."""


from netlist_carpentry.utils import CFG, LOG, initialize_logging, VERILOG_KEYWORDS  # Config and log must be loaded before the other modules
from netlist_carpentry.core.graph import EMPTY_GRAPH
from netlist_carpentry.core.enums import Direction, Signal
from netlist_carpentry.core.types import SignalArray
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
from netlist_carpentry.core.types.connectivity_data import ConnectivityData
from netlist_carpentry.core.graph import ModuleGraph
from netlist_carpentry.core.graph.pattern import EMPTY_PATTERN
from netlist_carpentry.utils import gate_factory, gate_lib
from netlist_carpentry.io.read.yosys import ReadConfig
from netlist_carpentry.io.read.read_utils import read_json, read, read_via_cfg, generate_json
from netlist_carpentry.io.write.write_utils import write
from netlist_carpentry.scripts import NC_SCRIPTS_DIR, run_equiv, run_eqy, run_equiv_miter
from netlist_carpentry.vis import show

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
    'ConnectivityData',
    'Direction',
    'Instance',
    'Module',
    'ModuleGraph',
    'NetlistElement',
    'Port',
    'PortSegment',
    'ReadConfig',
    'Signal',
    'SignalArray',
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
    'show',
    'write',
]


# Activate rudimentary LOG handling at first import
if not LOG._init_finished:
    initialize_logging()

yosys_path = shutil.which('yosys')
if not yosys_path:
    CFG.yosys_executable = 'yowasp-yosys'
    LOG.warn("Unable to locate default Yosys command 'yosys'. Falling back to 'yowasp-yosys'!")


def _in_jupyter() -> bool:
    try:
        from IPython import get_ipython  # type: ignore[attr-defined]
    except ImportError:
        return False

    shell = get_ipython()  # type: ignore
    return shell is not None and shell.__class__.__name__ == 'ZMQInteractiveShell'  # type: ignore
