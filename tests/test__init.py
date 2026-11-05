import os

import pytest

import netlist_carpentry as nc


def test_version() -> None:
    assert nc.__version__ == '0.6.1'


def test_yosys_path() -> None:
    if nc.yosys_path:
        assert 'bin' in nc.yosys_path
        assert 'yosys' in nc.yosys_path
    else:
        assert nc.CFG.yosys_executable == 'yowasp-yosys'


def test_exports() -> None:
    target_all = [
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
    assert nc.__all__ == target_all


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
