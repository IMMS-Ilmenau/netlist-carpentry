import os

import pytest
from pydantic import ValidationError

from netlist_carpentry import WIRE_SEGMENT_0, WIRE_SEGMENT_1, WIRE_SEGMENT_X, Circuit, Direction, Instance, Module, Signal
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.io.read.yosys.netlist_types import CellData, NetlistContent, PortData, PortDirections, WireData, YosysModule
from netlist_carpentry.utils.gate_lib import ADFF, DFFE, AndGate


def test_netlist_content() -> None:
    nc = NetlistContent(**{'foo!$§': 'bar.,?'})
    assert len(nc) == 1
    assert nc.model_dump(exclude_unset=True) == {'foo!$§': 'bar.,?'}


def test_netlist_content_try_get_int() -> None:
    assert NetlistContent._try_get_int('') == ''
    assert NetlistContent._try_get_int('abc') == 'abc'
    assert NetlistContent._try_get_int(42) == 42
    assert NetlistContent._try_get_int('0') == 0
    assert NetlistContent._try_get_int('0101') == 5


def test_build_metadata() -> None:
    m = Module(name='simpleAdder')
    YosysModule().build_metadata(m)

    assert len(m.metadata) == 0

    YosysModule(**{'attributes': {'foo': '42', 'bar': 'baz', 'qux': '000110100100'}}).build_metadata(m)

    assert m.metadata.yosys['foo'] == '42'
    assert m.metadata.yosys['bar'] == 'baz'
    assert m.metadata.yosys['qux'] == 420


def test_get_inst() -> None:
    m = Circuit(name='c').create_module('m')
    inst = CellData()._get_inst(m, {}, '§nonexisting_cell', 'inst')
    assert inst.module == m
    assert inst.name == 'inst'
    assert inst.instance_type == '§nonexisting_cell'
    assert not inst.is_primitive
    assert inst.is_blackbox
    assert not inst.is_module_instance

    inst = CellData()._get_inst(m, {}, '§and', 'inst2')
    assert isinstance(inst, AndGate)
    assert inst.name == 'inst2'
    assert inst.instance_type == '§and'
    assert inst.is_primitive
    assert not inst.is_blackbox
    assert not inst.is_module_instance

    inst = CellData()._get_inst(m, {'someModule'}, 'someModule', 'inst3')
    c = Circuit(name='c')
    c.create_module('someModule')
    inst.module = c.create_module('m')
    assert isinstance(inst, Instance)
    assert inst.name == 'inst3'
    assert inst.instance_type == 'someModule'
    assert not inst.is_primitive
    assert not inst.is_blackbox
    assert inst.is_module_instance


def test_build_instance_port_edge_cases() -> None:
    net_number_mapping = {2: WireSegmentPath(raw='test.w.0')}
    m = Module(name='test')
    m.create_wire('w')
    inst = Instance(name='instance', instance_type='§and', module=m)
    inst_dict = {'connections': {'A': [2]}, 'port_directions': {}}

    CellData(**inst_dict)._build_instance_ports(net_number_mapping, m, inst)
    assert len(inst.ports) == 1
    assert inst.ports['A'].direction == Direction.UNKNOWN
    assert inst.ports['A'][0].raw_ws_path == 'test.w.0'
    assert m.wires['w'][0].port_segments == [inst.ports['A'][0]]

    m.wires['w'][0].port_segments.clear()
    inst_dict.pop('port_directions')
    m.remove_instance(inst)
    inst = Instance(name='instance', instance_type='§and', module=m)
    CellData(**inst_dict)._build_instance_ports(net_number_mapping, m, inst)
    assert len(inst.ports) == 1
    assert inst.ports['A'].direction == Direction.UNKNOWN
    assert inst.ports['A'][0].raw_ws_path == 'test.w.0'
    assert m.wires['w'][0].port_segments == [inst.ports['A'][0]]


def test_build_instance_port_consts() -> None:
    net_number_mapping = {2: WireSegmentPath(raw='test.w.0')}
    m = Module(name='test')
    inst = Instance(name='instance', instance_type='§and', module=m)
    inst_dict = {'connections': {'A': ['0', '1', 'x']}, 'port_directions': {'A': 'input'}}

    CellData(**inst_dict)._build_instance_ports(net_number_mapping, m, inst)
    assert len(inst.ports) == 1
    assert len(inst.ports['A']) == 3
    assert inst.ports['A'][0].ws_path == WIRE_SEGMENT_0.path
    assert inst.ports['A'][1].ws_path == WIRE_SEGMENT_1.path
    assert inst.ports['A'][2].ws_path == WIRE_SEGMENT_X.path


def test_ports_dff() -> None:
    assert CellData()._new_port_names == {}

    dff_dict = CellData(**{'port_directions': {'ARST': 'input'}, 'connections': {'ARST': [2]}})
    assert dff_dict._new_port_names == {}
    assert dff_dict.ports == {'ARST': (Direction.IN, [2])}
    dff_dict.type = 'adff'
    assert dff_dict._new_port_names == {'ARST': 'RST'}
    assert dff_dict.ports == {'RST': (Direction.IN, [2])}

    dff_dict = CellData(**{'port_directions': {'ARST': 'input', 'SRST': 'input'}, 'connections': {'ARST': [2], 'SRST': [2]}})
    assert dff_dict._new_port_names == {}
    assert dff_dict.ports == {'ARST': (Direction.IN, [2]), 'SRST': (Direction.IN, [2])}
    dff_dict.type = 'adff'
    assert dff_dict._new_port_names == {'ARST': 'RST'}
    assert dff_dict.ports == {'RST': (Direction.IN, [2]), 'SRST': (Direction.IN, [2])}
    dff_dict.type = 'sdff'
    assert dff_dict._new_port_names == {'SRST': 'RST'}
    assert dff_dict.ports == {'ARST': (Direction.IN, [2]), 'RST': (Direction.IN, [2])}


def test_ports_mux() -> None:
    mux_dict = CellData(
        **{'port_directions': {'A': 'input', 'B': 'input', 'S': 'input', 'Y': 'output'}, 'connections': {'A': [2], 'B': [3], 'S': [4], 'Y': [5]}}
    )
    assert mux_dict._new_port_names == {}
    assert mux_dict.ports == {'A': (Direction.IN, [2]), 'B': (Direction.IN, [3]), 'S': (Direction.IN, [4]), 'Y': (Direction.OUT, [5])}
    mux_dict.type = 'mux'
    assert mux_dict._new_port_names == {'A': 'D0', 'B': 'D1'}
    assert mux_dict.ports == {'D0': (Direction.IN, [2]), 'D1': (Direction.IN, [3]), 'S': (Direction.IN, [4]), 'Y': (Direction.OUT, [5])}


def test_instance_post_processing() -> None:
    with pytest.warns(FutureWarning):
        inst = ADFF(name='abc', instance_type='§adff', module=None)
    inst_data = CellData(**{'parameters': {'ARST_VALUE': '001100'}})  # 12
    inst_data._update_all_param_types(inst)
    assert inst.rst_val_int == 12
    with pytest.raises(ValidationError):
        inst_data = CellData(**{'parameters': {'ARST_VALUE': 42}})
        inst_data._update_all_param_types(inst)
    inst_data = CellData(**{'parameters': {'ARST_POLARITY': '1'}})
    inst_data._update_all_param_types(inst)
    assert inst.rst_polarity == Signal.HIGH
    inst_data = CellData(**{'parameters': {'CLK_POLARITY': '0'}})
    inst_data._update_all_param_types(inst)
    assert inst.clk_polarity == Signal.LOW
    with pytest.warns(FutureWarning):
        inst = DFFE(name='abc', instance_type='§dffe', module=None)
    with pytest.raises(ValidationError):
        inst_data = CellData(**{'parameters': {'EN_POLARITY': False}})
        inst_data._update_all_param_types(inst)
    inst_data = CellData(**{'parameters': {'EN_POLARITY': '0'}})
    inst_data._update_all_param_types(inst)
    assert inst.en_polarity == Signal.LOW


def test_build_parameters() -> None:
    m = Module(name='simpleAdder')
    YosysModule().build_parameters(m)

    assert m.parameters == {}

    YosysModule(**{'parameter_default_values': {'foo': '42', 'bar': 'baz', 'qux': '000110100100'}}).build_parameters(m)

    assert m.parameters.foo == '42'
    assert m.parameters['foo'] == '42'

    assert m.parameters.bar == 'baz'
    assert m.parameters['bar'] == 'baz'

    assert m.parameters.qux == 420
    assert m.parameters['qux'] == 420


def test_deprecation_warnings() -> None:
    with pytest.warns(DeprecationWarning):
        from netlist_carpentry.io.read.yosys.netlist_types import PortAttributes

        assert PortAttributes is PortData
    with pytest.warns(DeprecationWarning):
        from netlist_carpentry.io.read.yosys.netlist_types import YosysCell

        assert YosysCell is CellData
    with pytest.warns(DeprecationWarning):
        from netlist_carpentry.io.read.yosys.netlist_types import Netnames

        assert Netnames is WireData
    with pytest.warns(DeprecationWarning):
        from netlist_carpentry.io.read.yosys.netlist_types import YosysPortDirections

        assert YosysPortDirections is PortDirections


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
