# mypy: disable-error-code="unreachable,comparison-overlap"
import copy
import json
import os
from pathlib import Path

import pytest

from netlist_carpentry import WIRE_SEGMENT_X
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.enums.direction import Direction as Dir
from netlist_carpentry.core.enums.element_type import EType
from netlist_carpentry.core.enums.signal import Signal
from netlist_carpentry.core.exceptions import (
    AlreadyConnectedError,
    EvaluationError,
    IdentifierConflictError,
    InvalidDirectionError,
    MultipleDriverError,
    ObjectLockedError,
    ObjectNotFoundError,
    PathResolutionError,
    SingleOwnershipError,
    StructureMismatchError,
    UnsupportedOperationError,
    WidthMismatchError,
)
from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.netlist_elements.element_path import (
    ElementPath,
    InstancePath,
    PortPath,
    PortSegmentPath,
    WirePath,
    WireSegmentPath,
)
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.wire_segment import WIRE_SEGMENT_0
from netlist_carpentry.utils.gate_factory import adff
from netlist_carpentry.utils.gate_lib import ADFFE, DFF, AndGate
from netlist_carpentry.utils.log import LOG


@pytest.fixture()
def empty_module() -> Module:
    from utils import empty_module as esm

    return esm()


@pytest.fixture()
def locked_module() -> Module:
    from utils import locked_module as im

    return im()


@pytest.fixture()
def standard_module() -> Module:
    from utils import empty_module as esm

    m = esm()
    w = m.create_wire('test_wire')
    p = m.create_port('test_port', Dir.IN_OUT)
    m.connect(w, p)
    m.create_instance(AndGate, 'test_instance')
    return m


@pytest.fixture()
def connected_module() -> Module:
    from utils import connected_module

    return connected_module()


@pytest.fixture()
def dff_module() -> Module:
    from utils import dff_module

    return dff_module()


@pytest.fixture()
def dff_circuit() -> Circuit:
    from utils import dff_circuit

    return dff_circuit()


def test_module_creation(empty_module: Module) -> None:
    assert empty_module.name == 'test_module1'
    assert empty_module.path.name == 'test_module1'
    assert empty_module.path.type is EType.MODULE
    assert empty_module.path.raw == 'test_module1'
    assert empty_module.type is EType.MODULE
    assert empty_module.parameters == {}
    assert empty_module.instances == {}
    assert empty_module.instances_by_types == {}
    assert empty_module.ports == {}
    assert empty_module.wires == {}
    assert empty_module.instances_with_constant_inputs == []
    assert empty_module.submodules == []
    assert empty_module.primitives == []
    assert empty_module.gatelib_primitives == []

    assert not empty_module.can_carry_signal


def test_eq(empty_module: Module) -> None:
    n2 = Module(raw_path=empty_module.raw_path)
    assert empty_module == n2

    n3 = Module(raw_path='wrong_path')
    assert empty_module != n3

    n4 = 'wrong_type'
    assert empty_module != n4
    assert empty_module.__eq__(n4) == NotImplemented


def test_circuit(empty_module: Module) -> None:
    assert not empty_module.has_circuit
    with pytest.raises(ObjectNotFoundError):
        empty_module.circuit

    c = Circuit(name='c')
    empty_module._circuit = c
    assert empty_module.has_circuit
    assert empty_module.circuit == c

    c = Circuit(name='c')
    m = c.create_module('m')
    assert m.has_circuit
    assert m.circuit == c


def test_input_ports(connected_module: Module) -> None:
    input_ports = connected_module.input_ports
    assert input_ports == [
        connected_module.ports['in1'],
        connected_module.ports['in2'],
        connected_module.ports['in3'],
        connected_module.ports['in4'],
        connected_module.ports['clk'],
        connected_module.ports['rst'],
    ]


def test_output_ports(connected_module: Module) -> None:
    output_ports = connected_module.output_ports
    assert output_ports == [connected_module.ports['out'], connected_module.ports['out_ff']]


def test_instances_with_constant_inputs(connected_module: Module) -> None:
    assert connected_module.instances_with_constant_inputs == [connected_module.instances['dff_inst']]

    connected_module.instances['and_inst'].ports['A'][0].set_ws_path(WIRE_SEGMENT_0.raw_path)
    assert connected_module.instances_with_constant_inputs == [connected_module.instances['and_inst'], connected_module.instances['dff_inst']]


def test_primitive_properties(connected_module: Module) -> None:
    c_insts = connected_module.instances
    insts = [c_insts['and_inst'], c_insts['or_inst'], c_insts['xor_inst'], c_insts['not_inst'], c_insts['dff_inst']]
    assert connected_module.primitives == insts
    assert connected_module.gatelib_primitives == insts


def test_valid_module_path(standard_module: Module) -> None:
    path = standard_module.ports['test_port'].path
    assert standard_module.valid_module_path(path)

    path = PortPath(raw='test_module1.test_port2')
    assert standard_module.valid_module_path(path)

    path = PortPath(raw='other_module.test_port1')
    assert not standard_module.valid_module_path(path)


def test_is_in_module(standard_module: Module) -> None:
    path = standard_module.ports['test_port'].path
    assert standard_module.is_in_module(path)

    path = PortPath(raw='test_module1.test_port2')
    assert not standard_module.is_in_module(path)

    path = PortPath(raw='other_module.test_port1')
    assert not standard_module.is_in_module(path)


def test_get_from_path(standard_module: Module) -> None:
    inst = standard_module.instances['test_instance']
    pname = 'test_inst_port'
    inst.connect(pname, WireSegmentPath(raw=f'{standard_module.name}.test_wire.0'), direction=Dir.IN)

    port = standard_module.get_from_path(PortPath(raw='test_module1.test_port'))
    assert port == standard_module.ports['test_port']
    with pytest.raises(PathResolutionError):
        standard_module.get_from_path(PortPath(raw='test_module1.invalid'))
    with pytest.raises(PathResolutionError):
        standard_module.get_from_path(PortPath(raw='test_module1.test_instance.invalid'))
    port_0 = standard_module.get_from_path(PortSegmentPath(raw='test_module1.test_port.0'))
    assert port_0 == standard_module.ports['test_port'][0]
    with pytest.raises(PathResolutionError):
        standard_module.get_from_path(PortSegmentPath(raw='test_module1.test_port.invalid'))
    port_0 = standard_module.get_from_path(PortSegmentPath(raw='test_module1.test_instance.test_inst_port.0'))
    assert port_0 == standard_module.instances['test_instance'].ports['test_inst_port'][0]
    with pytest.raises(PathResolutionError):
        standard_module.get_from_path(PortSegmentPath(raw='test_module1.test_instance.test_inst_port.inv'))
    wire = standard_module.get_from_path(WirePath(raw='test_module1.test_wire'))
    assert wire == standard_module.wires['test_wire']
    with pytest.raises(PathResolutionError):
        standard_module.get_from_path(WirePath(raw='test_module1.invalid'))
    wire_0 = standard_module.get_from_path(WireSegmentPath(raw='test_module1.test_wire.0'))
    assert wire_0 == standard_module.wires['test_wire'][0]
    with pytest.raises(IndexError):
        standard_module.get_from_path(WireSegmentPath(raw='test_module1.test_wire.69420'))
    with pytest.raises(PathResolutionError):
        standard_module.get_from_path(WireSegmentPath(raw='test_module1.test_wire.invalid'))
    wire_0 = standard_module.get_from_path(WireSegmentPath(raw='0'))
    assert wire_0 == WIRE_SEGMENT_0
    instance = standard_module.get_from_path(InstancePath(raw='test_module1.test_instance'))
    assert instance == standard_module.instances['test_instance']
    with pytest.raises(PathResolutionError):
        standard_module.get_from_path(InstancePath(raw='test_module1.invalid'))
    with pytest.raises(PathResolutionError):
        standard_module.get_from_path(ElementPath(raw='test_module1.invalid'))
    with pytest.raises(PathResolutionError):
        standard_module.get_from_path(PortPath(raw='other_module.test_port'))


def test_add_instance(empty_module: Module, locked_module: Module) -> None:
    from utils import standard_instance_with_ports

    assert empty_module.instances == {}
    i = standard_instance_with_ports(init_module=False)
    added = empty_module.add_instance(i)
    assert added == i
    assert len(empty_module.instances) == 1
    assert empty_module.instances[i.name] == i

    m2 = Module(raw_path='m2')
    with pytest.raises(SingleOwnershipError):
        m2.add_instance(i)

    # no two instances with same name can be added, so len should still be 1
    # i2 does not replace i, since this would probably not be intended
    i2 = standard_instance_with_ports(init_module=False)
    i2.instance_type = 'foo'
    assert i2 is not i
    with pytest.raises(IdentifierConflictError):
        empty_module.add_instance(i2)
    assert len(empty_module.instances) == 1
    assert empty_module.instances[i.name] == i

    i3 = standard_instance_with_ports()
    empty_module.create_port('double')
    i3.raw_path = 'test_module1.double'
    with pytest.raises(IdentifierConflictError):
        empty_module.add_wire(i3)

    assert len(locked_module.instances) == 1
    i.module = None
    with pytest.raises(ObjectLockedError):
        locked_module.add_instance(i)
    assert len(locked_module.instances) == 1


def test_create_instance(empty_module: Module, connected_module: Module) -> None:
    c = Circuit(name='c')
    connected_module.set_name('m2')
    c.add_module(connected_module)
    c.add_module(empty_module)
    inst = empty_module.create_instance(connected_module, 'test_inst')
    assert inst == empty_module.instances['test_inst']
    assert inst.instance_type == connected_module.name
    assert inst.ports.keys() == connected_module.ports.keys()
    assert empty_module.circuit.instances['m2'] == [InstancePath(raw='test_module1.test_inst')]
    for p in inst.ports:
        assert inst.ports[p].direction == connected_module.ports[p].direction
        assert inst.ports[p].width == connected_module.ports[p].width

    inst = empty_module.create_instance(connected_module, 'test_inst2')
    assert empty_module.circuit.instances['m2'] == [InstancePath(raw='test_module1.test_inst'), InstancePath(raw='test_module1.test_inst2')]

    with pytest.raises(IdentifierConflictError):
        empty_module.create_instance(connected_module, 'test_inst')

    inst = empty_module.create_instance(connected_module)
    assert inst.name == f'_{connected_module.name}_0_'
    inst = empty_module.create_instance(connected_module)
    assert inst.name == f'_{connected_module.name}_1_'
    empty_module._inst_gen_i = 0
    inst = empty_module.create_instance(connected_module)
    assert inst.name == f'_{connected_module.name}_2_'


def test_create_instance_gatelib(empty_module: Module) -> None:
    from netlist_carpentry.utils.gate_lib import XorGate

    empty_module.create_instance(XorGate, 'xor')
    assert len(empty_module.instances) == 1
    assert 'xor' in empty_module.instances
    assert isinstance(empty_module.instances['xor'], XorGate)

    empty_module.create_instance(XorGate, 'xor2', params={'Y_WIDTH': 8})
    assert len(empty_module.instances) == 2
    assert 'xor2' in empty_module.instances
    assert empty_module.instances['xor2'].ports['A'].width == 8
    assert empty_module.instances['xor2'].ports['B'].width == 8
    assert empty_module.instances['xor2'].ports['Y'].width == 8

    inst = empty_module.create_instance(XorGate)
    assert inst.name == '_XorGate_0_'
    inst = empty_module.create_instance(XorGate)
    assert inst.name == '_XorGate_1_'
    empty_module._inst_gen_i = 0
    inst = empty_module.create_instance(XorGate)
    assert inst.name == '_XorGate_2_'


def test_copy_instance(standard_module: Module) -> None:
    inst = standard_module.instances['test_instance']

    inst2 = standard_module.copy_instance(inst, 'inst2')
    assert 'inst2' in standard_module.instances
    assert inst2 is standard_module.instances['inst2']
    assert inst2.instance_type == inst.instance_type
    for pname, p in inst.ports.items():
        assert pname in inst2.ports
        assert p.width == inst2.ports[pname].width
        assert p.direction == inst2.ports[pname].direction
        assert p.offset == inst2.ports[pname].offset
        assert inst2.ports[pname].is_unconnected

    inst3 = standard_module.copy_instance('test_instance', 'inst3')
    assert 'inst3' in standard_module.instances
    assert inst3 is standard_module.instances['inst3']
    assert inst3.instance_type == inst.instance_type
    for pname, p in inst.ports.items():
        assert pname in inst3.ports
        assert p.width == inst3.ports[pname].width
        assert p.direction == inst3.ports[pname].direction
        assert p.offset == inst3.ports[pname].offset
        assert inst3.ports[pname].is_unconnected

    with pytest.raises(IdentifierConflictError):
        standard_module.copy_instance(inst, 'inst2')


def test_copy_instance_keep_inputs(standard_module: Module) -> None:
    inst = standard_module.instances['test_instance']
    for pname in inst.ports:
        standard_module.connect(standard_module.wires['test_wire'][0], inst.ports[pname][0])
        assert inst.ports[pname].is_connected

    inst2 = standard_module.copy_instance(inst, 'inst2', keep_inputs=True)
    assert 'inst2' in standard_module.instances
    assert inst2 is standard_module.instances['inst2']
    assert inst2.instance_type == inst.instance_type
    for pname, p in inst.ports.items():
        assert pname in inst2.ports
        assert p.width == inst2.ports[pname].width
        assert p.direction == inst2.ports[pname].direction
        assert p.offset == inst2.ports[pname].offset
        if p.is_output:
            assert inst2.ports[pname].is_unconnected
        else:
            assert inst2.ports[pname].is_connected
            assert inst2.ports[pname][0].ws == standard_module.wires['test_wire'][0]


def test_change_instance_type(dff_module: Module) -> None:
    c = Circuit(name='c')
    c.add_module(dff_module)
    m = c.create_module('m')
    with pytest.raises(ObjectNotFoundError):
        dff_module.change_instance_type('bad_name', m)

    dff = dff_module.instances['dff_inst']
    with pytest.raises(StructureMismatchError):
        dff_module.change_instance_type(dff, m)

    assert dff.instance_type == '§dff'
    assert isinstance(dff, DFF)
    assert dff.is_primitive
    assert dff.is_sequential
    m.create_port('D')
    m.create_port('CLK')
    m.create_port('Q')

    dff_module.change_instance_type(dff, m)
    dff2 = dff_module.instances['dff_inst']

    assert dff2.instance_type == 'm'
    assert not dff2.is_primitive
    assert dff2.is_module_instance
    assert not isinstance(dff2, DFF)

    assert dff.ports == dff2.ports


def test_replace_instance(dff_module: Module) -> None:
    adffe = ADFFE(raw_path=f'{dff_module.name}.adffe_inst')
    with pytest.raises(ObjectNotFoundError):
        dff_module.replace('lulz no instance', adffe)

    dff = dff_module.instances_by_types['§dff'][0]
    with pytest.raises(IdentifierConflictError):
        dff_module.replace(dff, dff)
    with pytest.raises(WidthMismatchError):
        dff_module.replace(dff, adffe)

    adffe = ADFFE(raw_path=f'{dff_module.name}.adffe_inst', parameters={'WIDTH': 4})
    assert dff.name in dff_module.instances
    assert adffe.name not in dff_module.instances
    for p in dff.ports.values():
        assert p.is_connected
    for p in adffe.ports.values():
        assert p.is_unconnected
    dff_connections = dff.connections
    warns = LOG.warns_quantity
    dff_module.replace(dff, adffe)
    assert LOG.warns_quantity == warns + 2
    assert dff.name not in dff_module.instances
    assert adffe.name in dff_module.instances
    assert adffe.ports['D'].is_connected
    assert adffe.ports['D'].connected_wire_segments == dff_connections['D']
    assert adffe.ports['CLK'].is_connected
    assert adffe.ports['CLK'].connected_wire_segments == dff_connections['CLK']
    assert adffe.ports['RST'].is_unconnected
    assert adffe.ports['EN'].is_unconnected
    assert adffe.ports['Q'].is_connected
    assert adffe.ports['Q'].connected_wire_segments == dff_connections['Q']

    with pytest.raises(StructureMismatchError):
        dff_module.connect(dff_module.ports['CLK'], adffe.ports['RST'])
        dff_module.replace(adffe, dff)

    adffe.disconnect('RST')
    dff_module.replace(adffe, dff)
    assert '§adffe' not in dff_module.instances_by_types
    assert '§dff' in dff_module.instances_by_types


def test_replace_instance_silent(dff_module: Module) -> None:
    dff = dff_module.instances_by_types['§dff'][0]
    adffe = ADFFE(raw_path=f'{dff_module.name}.adffe_inst', parameters={'WIDTH': 4})
    warns = LOG.warns_quantity
    dff_module.replace(dff, adffe, silent=True)
    assert LOG.warns_quantity == warns


def test_add_instance_multi_type(standard_module: Module) -> None:
    assert len(standard_module.instances_by_types['§and']) == 1

    is_added = standard_module.add_instance(Instance(raw_path='test_module1.test_instance2', instance_type='§and', module=None))

    assert is_added
    assert len(standard_module.instances) == 2
    assert len(standard_module.instances_by_types) == 1
    assert len(standard_module.instances_by_types['§and']) == 2


def test_remove_instance(empty_module: Module, locked_module: Module, connected_module: Module) -> None:
    from utils import standard_instance_with_ports, wire_4b

    assert len(empty_module.instances) == 0
    c = Circuit(name='c')
    c.add_module(empty_module)

    i = standard_instance_with_ports(init_module=False)
    w4 = wire_4b(init_module=False)
    empty_module.add_instance(i)
    assert i.module == empty_module
    assert c.instances['test_module1'] == []
    empty_module.add_wire(w4)
    assert len(empty_module.instances) == 1

    empty_module.remove_instance(i)
    assert len(empty_module.instances) == 0
    assert i.module is None

    m2 = Module(raw_path='m2')
    i = empty_module.create_instance(m2, 'inst2')
    empty_module.remove_instance(i)
    assert len(empty_module.instances) == 0
    assert i.module is None

    c.add_module(m2)
    i = empty_module.create_instance(m2, 'inst2')
    assert c.instances['m2'] == [i.path]
    empty_module.remove_instance(i)
    assert len(empty_module.instances) == 0
    assert i.module is None
    assert c.instances['m2'] == []

    with pytest.raises(ObjectNotFoundError):
        empty_module.remove_instance(i)

    assert len(locked_module.instances) == 1
    with pytest.raises(ObjectLockedError):
        locked_module.remove_instance('test_inst')
    assert len(locked_module.instances) == 1

    assert len(connected_module.instances) == 5
    inst = connected_module.instances['not_inst']
    nodes = connected_module.get_edges(inst)
    for port_name, conn_dict in nodes.items():
        for ws in conn_dict.values():
            assert any(f'{inst.name}.{port_name}' in ps.raw_path for ps in ws.port_segments)
    connected_module.remove_instance('not_inst')
    assert len(connected_module.instances) == 4
    for port_name, conn_dict in nodes.items():
        for ws in conn_dict.values():
            assert not any(f'{inst.name}.{port_name}' in ps.raw_path for ps in ws.port_segments)


def test_get_instance(standard_module: Module) -> None:
    inst = standard_module.get_instance('test_instance')
    assert inst is not None
    assert inst == standard_module.instances['test_instance']

    inst = standard_module.get_instance('invalid')
    assert inst is None


def test_get_instances(standard_module: Module) -> None:
    c = Circuit(name='c')
    c.add_module(standard_module)
    standard_module.add_instance(Instance(raw_path='test_module1.test_instance2', instance_type='$and', module=None))

    i1 = standard_module.get_instances(name='test_instance')
    assert i1 == [standard_module.instances['test_instance']]
    i2 = standard_module.get_instances(name='test_instance', fuzzy=True)
    assert i2 == [standard_module.instances['test_instance'], standard_module.instances['test_instance2']]
    i3 = standard_module.get_instances(type='$and')
    assert i3 == [standard_module.instances['test_instance2']]
    i4 = standard_module.get_instances(type='and', fuzzy=True)
    assert i4 == [standard_module.instances['test_instance'], standard_module.instances['test_instance2']]
    i5 = standard_module.get_instances()
    assert i5 == []
    i6 = standard_module.get_instances(name='test_instance', type='$and')
    assert i6 == []

    m2 = c.add_module(Module(raw_path='m2'))
    inst3 = m2.create_instance(c.add_module(Module(raw_path='some_and')), instance_name='test_instance3')
    standard_module.create_instance(m2, 'inst2')

    i2 = standard_module.get_instances(name='test_instance', fuzzy=True)
    assert i2 == [standard_module.instances['test_instance'], standard_module.instances['test_instance2']]
    i2 = standard_module.get_instances(name='test_instance', fuzzy=True, recursive=True)
    assert i2 == [standard_module.instances['test_instance'], standard_module.instances['test_instance2'], inst3]

    i2 = standard_module.get_instances(type='and', fuzzy=True)
    assert i2 == [standard_module.instances['test_instance'], standard_module.instances['test_instance2']]
    i2 = standard_module.get_instances(type='and', fuzzy=True, recursive=True)
    assert i2 == [standard_module.instances['test_instance'], standard_module.instances['test_instance2'], inst3]


def test_add_port(empty_module: Module, locked_module: Module) -> None:
    from utils import standard_port_in, standard_port_out

    assert empty_module.ports == {}
    p = standard_port_in(init_module=False)
    added = empty_module.add_port(p)
    assert added == p
    assert len(empty_module.ports) == 1
    assert empty_module.ports[p.name] == p

    m2 = Module(raw_path='m2')
    with pytest.raises(SingleOwnershipError):
        m2.add_port(p)

    # no two ports with same name can be added, so len should still be 1
    # p2 does not replace p, since this would probably not be intended
    p2 = standard_port_out()
    p2.set_name(p.name)
    p2.module_or_instance = None
    with pytest.raises(IdentifierConflictError):
        empty_module.add_port(p2)
    assert len(empty_module.ports) == 1
    assert empty_module.ports[p.name] == p

    p3 = standard_port_out()
    empty_module.create_instance(Module(raw_path='m2'), 'double')
    p3.raw_path = 'test_module1.double'
    with pytest.raises(IdentifierConflictError):
        empty_module.add_port(p3)

    assert len(locked_module.ports) == 1
    p.module_or_instance = None
    with pytest.raises(ObjectLockedError):
        locked_module.add_port(p)
    assert len(locked_module.ports) == 1


def test_create_port(empty_module: Module, locked_module: Module) -> None:
    from utils import standard_port_in

    empty_module.create_wire('test_wire1')
    w_raw_path = f'{empty_module.name}.test_wire1'
    ws_raw_path = f'{empty_module.name}.test_wire1.0'
    w_path = WirePath(raw=w_raw_path)
    ws_path = WireSegmentPath(raw=ws_raw_path)

    assert empty_module.ports == {}
    p = standard_port_in()
    added = empty_module.create_port(p.name, direction=p.direction, is_locked=True)
    empty_module.connect(w_path, added)
    assert added == empty_module.ports[p.name]
    assert len(empty_module.ports) == 1
    assert empty_module.ports[p.name].name == p.name
    assert empty_module.ports[p.name].direction == p.direction
    assert empty_module.ports[p.name].path.raw == empty_module.path.raw + '.' + p.name
    assert empty_module.ports[p.name].locked
    assert not empty_module.ports[p.name].is_instance_port
    assert len(empty_module.ports[p.name].segments) == 1

    with pytest.raises(IdentifierConflictError):
        empty_module.create_port(p.name, direction=p.direction, is_locked=True).change_connection(ws_path)
    assert len(empty_module.ports) == 1

    assert len(locked_module.ports) == 1
    with pytest.raises(ObjectLockedError):
        locked_module.create_port(p.name).change_connection(ws_path)
    assert len(locked_module.ports) == 1

    empty_module.create_port('port8b', direction=Dir.IN, width=8, offset=4)
    assert 'port8b' in empty_module.ports
    assert empty_module.ports['port8b'].width == 8
    assert {4, 5, 6, 7, 8, 9, 10, 11} == set(empty_module.ports['port8b'].segments.keys())


def test_create_port_check_dependencies(connected_module: Module) -> None:
    w_path = WireSegmentPath(raw='test_module1.in1.0')
    w_path_invalid = WireSegmentPath(raw='test_module1.in1.seg1')
    w = connected_module.wires['in1']
    assert len(w[0].port_segments) == 2  # Two already connected because of initialization (Input port connected to wire + And-Gate)
    added = connected_module.create_port('test_port', Dir.OUT, width=0)
    assert added == connected_module.ports['test_port']
    p = connected_module.ports['test_port']
    assert not p.segments
    assert len(w[0].port_segments) == 2

    added = connected_module.create_port('test_port2', Dir.OUT)
    connected_module.connect(w_path, added)
    assert added == connected_module.ports['test_port2']
    p = connected_module.ports['test_port2']
    assert p[0].is_connected
    assert p[0].ws_path == w_path
    assert len(w[0].port_segments) == 3

    added = connected_module.create_port('test_port3', Dir.OUT)
    with pytest.raises(PathResolutionError):
        connected_module.connect(w_path_invalid, added)
    assert added == connected_module.ports['test_port3']
    p = connected_module.ports['test_port3']
    assert len(w[0].port_segments) == 3


def test_remove_port(empty_module: Module, locked_module: Module) -> None:
    from utils import standard_port_in

    assert len(empty_module.ports) == 0

    p = standard_port_in(init_module=False)
    empty_module.add_port(p)
    assert p.module_or_instance is empty_module
    assert len(empty_module.ports) == 1

    empty_module.remove_port(p)
    assert len(empty_module.ports) == 0
    assert p.module_or_instance is None

    with pytest.raises(ObjectNotFoundError):
        empty_module.remove_port(p)

    assert len(locked_module.ports) == 1
    with pytest.raises(ObjectLockedError):
        locked_module.remove_port('test_port')
    assert len(locked_module.ports) == 1


def test_get_port(standard_module: Module) -> None:
    inst = standard_module.get_port('test_port')
    assert inst is not None
    assert inst == standard_module.ports['test_port']

    inst = standard_module.get_port('invalid')
    assert inst is None


def test_get_ports(standard_module: Module) -> None:
    from utils import standard_port_in, standard_port_out

    standard_module.add_port(standard_port_in(init_module=False))
    standard_module.add_port(standard_port_out(init_module=False))

    p1 = standard_module.get_ports(name='test_port')
    assert p1 == [standard_module.ports['test_port']]
    p2 = standard_module.get_ports(name='test_port', fuzzy=True)
    assert p2 == [standard_module.ports['test_port'], standard_module.ports['test_port1'], standard_module.ports['test_port2']]
    p3 = standard_module.get_ports(direction=Dir.IN)
    assert p3 == [standard_module.ports['test_port1']]
    p4 = standard_module.get_ports(direction=Dir.IN, fuzzy=True)
    assert p4 == [standard_module.ports['test_port'], standard_module.ports['test_port1']]
    p5 = standard_module.get_ports()
    assert p5 == []
    p6 = standard_module.get_ports(name='test_port', direction=Dir.IN)
    assert p6 == []


def test_add_wire(empty_module: Module, locked_module: Module) -> None:
    from utils import standard_wire

    assert empty_module.wires == {}
    w = standard_wire()
    is_added = empty_module.add_wire(w)
    assert is_added
    assert len(empty_module.wires) == 1
    assert empty_module.wires[w.name] == w

    m2 = Module(raw_path='m2')
    with pytest.raises(SingleOwnershipError):
        m2.add_wire(w)

    # no two wires with same name can be added, so len should still be 1
    # w2 does not replace w, since this would probably not be intended
    w2 = standard_wire()
    w2.segments.pop(1)
    assert w2 != w
    with pytest.raises(IdentifierConflictError):
        empty_module.add_wire(w2)
    assert len(empty_module.wires) == 1
    assert empty_module.wires[w.name] == w

    w3 = standard_wire()
    empty_module.create_port('double')
    w3.raw_path = 'test_module1.double'
    with pytest.raises(IdentifierConflictError):
        empty_module.add_wire(w3)

    assert len(locked_module.wires) == 1
    w.module = None
    with pytest.raises(ObjectLockedError):
        locked_module.add_wire(w)
    assert len(locked_module.wires) == 1


def test_create_wire(empty_module: Module, locked_module: Module) -> None:
    from utils import standard_wire

    assert empty_module.wires == {}
    w = standard_wire()
    added = empty_module.create_wire(w.name, width=len(w), is_locked=True, offset=1)
    assert added == empty_module.wires[w.name]
    assert len(empty_module.wires) == 1
    assert empty_module.wires[w.name].name == w.name
    assert empty_module.wires[w.name].path.raw == empty_module.path.raw + '.' + w.name
    assert empty_module.wires[w.name].locked
    assert empty_module.wires[w.name].signal_array == w.signal_array
    assert len(empty_module.wires[w.name].segments) == len(w)

    # no two wires with same name can be added, so len should still be 1
    # w2 does not replace w, since this would probably not be intended
    w2 = standard_wire()
    w2.segments.pop(1)
    assert w2 != w
    with pytest.raises(IdentifierConflictError):
        empty_module.create_wire(w2.name)
    assert len(empty_module.wires) == 1
    assert empty_module.wires[w.name].name == w.name

    assert len(locked_module.wires) == 1
    with pytest.raises(ObjectLockedError):
        locked_module.create_wire(w.name)
    assert len(locked_module.wires) == 1


def test__create_generic_wire(empty_module: Module) -> None:
    assert empty_module._wire_gen_i == 0
    empty_module._create_generic_wire()
    assert len(empty_module.wires) == 1
    assert '_ncgen_0_' in empty_module.wires
    assert empty_module._wire_gen_i == 0

    empty_module._create_generic_wire()
    assert len(empty_module.wires) == 2
    assert '_ncgen_0_' in empty_module.wires
    assert '_ncgen_1_' in empty_module.wires
    assert empty_module._wire_gen_i == 1

    empty_module._wire_gen_i = 0
    empty_module._create_generic_wire()  # _wire_gen_i should be updated correctly
    assert len(empty_module.wires) == 3
    assert '_ncgen_0_' in empty_module.wires
    assert '_ncgen_1_' in empty_module.wires
    assert '_ncgen_2_' in empty_module.wires
    assert empty_module._wire_gen_i == 2


def test_remove_wire(empty_module: Module, locked_module: Module, connected_module: Module) -> None:
    from utils import standard_wire

    assert len(empty_module.wires) == 0

    w = standard_wire()
    w[1].port_segments.clear()
    empty_module.add_wire(w)
    assert len(empty_module.wires) == 1
    assert w.module is empty_module

    empty_module.remove_wire(w)
    assert len(empty_module.wires) == 0
    assert w.module is None

    with pytest.raises(ObjectNotFoundError):
        empty_module.remove_wire(w)

    assert len(locked_module.wires) == 1
    with pytest.raises(ObjectLockedError):
        locked_module.remove_wire('test_wire')
    assert len(locked_module.wires) == 1

    assert len(connected_module.wires) == 12
    w = connected_module.wires['wire_or']
    ports = connected_module.get_wire_ports(w[0].path)
    for ps in ports:
        assert ps in w[0].port_segments
        assert w[0].path == ps.ws_path
    connected_module.remove_wire('wire_or')
    assert len(connected_module.wires) == 11
    for ps in ports:
        assert ps not in w[0].port_segments
        assert ps.ws_path == WIRE_SEGMENT_X.path


def test_get_wire(standard_module: Module) -> None:
    inst = standard_module.get_wire('test_wire')
    assert inst is not None
    assert inst == standard_module.wires['test_wire']

    inst = standard_module.get_wire('invalid')
    assert inst is None


def test_get_wires(standard_module: Module) -> None:
    from utils import standard_wire

    standard_module.add_wire(standard_wire())

    p1 = standard_module.get_wires(name='test_wire')
    assert p1 == [standard_module.wires['test_wire']]
    p2 = standard_module.get_wires(name='wire', fuzzy=True)
    assert p2 == [standard_module.wires['test_wire'], standard_module.wires['wire1']]
    p3 = standard_module.get_wires()
    assert p3 == []


def test_name_occupied(standard_module: Module) -> None:
    assert standard_module.name_occupied('test_wire')
    assert standard_module.name_occupied('test_port')
    assert standard_module.name_occupied('test_instance')
    assert not standard_module.name_occupied('unoccupied_name')


def test_connect(standard_module: Module) -> None:
    standard_module.create_wire('test_wire2')
    standard_module.create_port('test_port2', direction=Dir.IN)
    w = standard_module.wires['test_wire2']
    p = standard_module.ports['test_port2']
    p.segments.clear()
    p.create_port_segment(0)
    assert w.ports == {0: []}
    assert p[0].ws_path == WIRE_SEGMENT_X.path
    assert not p.is_connected_partly

    standard_module.connect(w[0], p[0])
    assert w.ports == {0: [p[0]]}
    assert p[0].ws_path == w[0].path

    standard_module.disconnect(p[0])
    standard_module.connect(WIRE_SEGMENT_0, p[0])
    assert WIRE_SEGMENT_0.port_segments == []
    assert p[0].ws_path == WIRE_SEGMENT_0.path

    with pytest.raises(AlreadyConnectedError):
        standard_module.connect(w[0], p[0])

    standard_module.disconnect(p)
    with pytest.raises(UnsupportedOperationError):
        standard_module.connect(p, p[0])

    standard_module.disconnect(p)
    standard_module.change_mutability(is_now_locked=True)
    standard_module.connect(w[0], p[0])
    assert p.is_unconnected

    standard_module.change_mutability(is_now_locked=False)
    w[0].change_mutability(is_now_locked=True)
    standard_module.connect(w[0], p[0])
    assert p.is_unconnected


def test_connect_full_port_wire(standard_module: Module) -> None:
    standard_module.create_wire('test_wire2', width=8)
    standard_module.create_port('test_port2', direction=Dir.IN)
    w = standard_module.wires['test_wire2']
    p = standard_module.ports['test_port2']
    p.segments.clear()
    p.create_port_segments(8)
    assert w.ports == {0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: [], 7: []}
    assert p[0].ws_path == WIRE_SEGMENT_X.path
    assert not p.is_connected_partly

    standard_module.connect(w, p)
    assert w.ports == {0: [p[0]], 1: [p[1]], 2: [p[2]], 3: [p[3]], 4: [p[4]], 5: [p[5]], 6: [p[6]], 7: [p[7]]}
    assert p[0].ws_path == w[0].path
    assert p.is_connected

    p.create_port_segments(1, offset=8)
    standard_module.disconnect(p)
    with pytest.raises(WidthMismatchError):
        standard_module.connect(w, p)


def test_connect_inst_port(standard_module: Module) -> None:
    standard_module.create_wire('test_wire2')
    inst = standard_module.instances['test_instance']
    inst.connect('test_inst_port', None, Dir.IN)
    assert 'test_inst_port' in inst.ports
    assert 'test_inst_port' in inst.connections

    w = standard_module.wires['test_wire2']
    p = inst.ports['test_inst_port']

    standard_module.connect(w[0], p[0])
    assert w.ports == {0: [p[0]]}
    assert p[0].ws_path == w[0].path
    assert inst.connections[p.name][0] == w[0].path


def test_connect_ports(standard_module: Module) -> None:
    p2 = standard_module.create_port('test_port2', direction=Dir.IN, width=8)
    p3 = standard_module.create_port('test_port3', direction=Dir.OUT, width=8, offset=1)
    assert p2.is_unconnected
    assert p3.is_unconnected

    standard_module.connect(p2[0], p3[1])
    assert p2.is_connected_partly
    assert p3.is_connected_partly
    assert p2[0].is_connected
    assert p3[1].is_connected
    assert p2[0].ws_path == p3[1].ws_path

    standard_module.connect(p2[1].path, p3[2].path)
    assert p2.is_connected_partly
    assert p3.is_connected_partly
    assert p2[1].is_connected
    assert p3[2].is_connected
    assert p2[1].ws_path == p3[2].ws_path

    standard_module.disconnect(p3)
    standard_module.connect(p2, p3)
    assert p2.is_connected
    assert p3.is_connected
    for i in range(8):
        assert p2[i].ws_path == p3[i + 1].ws_path

    p4 = standard_module.create_port('test_port4', direction=Dir.IN, width=8, offset=1)
    with pytest.raises(InvalidDirectionError):
        standard_module.connect(p2, p4)

    p5 = standard_module.create_port('test_port5', direction=Dir.OUT, width=1, offset=1)
    with pytest.raises(WidthMismatchError):
        standard_module.connect(p2, p5)


def test_connect_cases(empty_module: Module) -> None:
    W = empty_module.create_wire('W')
    D = empty_module.create_port('D', direction=Dir.IN)
    L = empty_module.create_port('L', direction=Dir.OUT)
    L2 = empty_module.create_port('L2', direction=Dir.OUT)

    # Valid cases
    # Unconnected -> Unconnected
    empty_module.connect(D, L)
    assert D.is_connected
    assert D.connected_wires == L.connected_wires
    empty_module.disconnect(D)
    empty_module.disconnect(L)

    empty_module.connect(L, L2)
    assert L.is_connected
    assert L.connected_wires == L2.connected_wires
    empty_module.disconnect(L)
    empty_module.disconnect(L2)

    # Connected -> Unconnected
    empty_module.connect(W, D)  # Driver already connected
    empty_module.connect(D, L)
    assert D.connected_wires == L.connected_wires
    assert L.connected_wires == {W.path}
    empty_module.disconnect(D)
    empty_module.disconnect(L)

    empty_module.connect(W, L2)  # Load already connected
    empty_module.connect(L2, L)
    assert L.connected_wires == L2.connected_wires
    assert L.connected_wires == {W.path}
    empty_module.disconnect(L)

    assert L2.connected_wires == {W.path}
    with pytest.raises(AlreadyConnectedError):
        empty_module.connect(D, L2)  # Forbidden case: second element may not be connected already!

    with pytest.raises(InvalidDirectionError):
        empty_module.connect(L, D)  # Forbidden case: second element may not be a driver!


def test_disconnect(connected_module: Module) -> None:
    pseg = connected_module.ports['in1'][0]

    connected_module.change_mutability(True, recursive=True)
    assert pseg.is_connected
    with pytest.raises(ObjectLockedError):
        connected_module.disconnect(pseg)
    assert pseg.is_connected
    connected_module.change_mutability(False, recursive=True)

    connected_module.disconnect(pseg)
    assert not pseg.is_connected

    connected_module.disconnect(pseg)
    assert not pseg.is_connected


def test_disconnect_ports(connected_module: Module) -> None:
    p = connected_module.ports['in1']

    connected_module.change_mutability(True, recursive=True)
    assert p.is_connected
    with pytest.raises(ObjectLockedError):
        connected_module.disconnect(p)
    assert p.is_connected
    connected_module.change_mutability(False, recursive=True)

    connected_module.disconnect(p)
    assert not p.is_connected

    connected_module.disconnect(p)
    assert not p.is_connected


def test_disconnect_inst_port(connected_module: Module) -> None:
    w = connected_module.wires['in1']
    inst = connected_module.instances['and_inst']
    p = inst.ports['A']
    pseg = p[0]

    assert len(w.ports[0]) == 2
    assert pseg in w.ports[0]
    connected_module.disconnect(pseg)
    assert len(w.ports[0]) == 1
    assert pseg not in w.ports[0]
    assert pseg.ws_path == WIRE_SEGMENT_X.path
    assert inst.connections[p.name][0] == WIRE_SEGMENT_X.path


def test_disconnect_inst_port_path(connected_module: Module) -> None:
    w = connected_module.wires['in1']
    inst = connected_module.instances['and_inst']
    p = inst.ports['A']
    pseg = p[0]

    assert len(w.ports[0]) == 2
    assert pseg in w.ports[0]
    connected_module.disconnect(p.path)
    assert len(w.ports[0]) == 1
    assert pseg not in w.ports[0]
    assert pseg.ws_path == WIRE_SEGMENT_X.path
    assert inst.connections[p.name][0] == WIRE_SEGMENT_X.path


def test_update_module_instances() -> None:
    m = Module(raw_path='m')

    with pytest.raises(ObjectNotFoundError):
        m.update_module_instances()

    c = Circuit(name='c')
    m1 = c.create_module('m1')
    m2 = c.create_module('m2')
    assert c.instances == {}
    inst_m2 = m1.create_instance(m2, 'inst')
    assert c.instances == {'m2': [InstancePath(raw='m1.inst')]}

    p1 = m2.create_port('p1', offset=3, width=4)
    assert inst_m2.ports == {}
    m2.update_module_instances()
    assert inst_m2.ports['p1'].name == p1.name

    m2.remove_port('p1')
    assert inst_m2.ports['p1'].name == p1.name
    m2.update_module_instances()
    assert inst_m2.ports == {}


def test_get_edges(connected_module: Module) -> None:
    with pytest.raises(KeyError):
        connected_module.get_edges('non_existing')
    inst_and = connected_module.instances['and_inst']
    edges = connected_module.get_edges(inst_and)
    assert len(edges) == 3
    assert ['A', 'B', 'Y'] == list(edges.keys())
    assert len(edges['A']) == 1
    assert len(edges['B']) == 1
    assert len(edges['Y']) == 1
    assert edges['A'][0] == connected_module.wires['in1'][0]
    assert edges['B'][0] == connected_module.wires['in2'][0]
    assert edges['Y'][0] == connected_module.wires['wire_and'][0]

    inst_and.connect('C', None)
    edges = connected_module.get_edges(inst_and)
    assert len(edges) == 4
    assert ['A', 'B', 'Y', 'C'] == list(edges.keys())
    assert edges['C'][0] == WIRE_SEGMENT_X


def test_get_outgoing_edges(connected_module: Module) -> None:
    with pytest.raises(KeyError):
        connected_module.get_outgoing_edges('non_existing')
    inst_and = connected_module.instances['and_inst']
    edges = connected_module.get_outgoing_edges(inst_and.name)
    assert len(edges) == 1
    assert ['Y'] == list(edges.keys())
    assert len(edges['Y']) == 1
    assert edges['Y'][0] == connected_module.wires['wire_and'][0]

    inst_and.connect('C', None, Dir.OUT)
    edges = connected_module.get_outgoing_edges(inst_and.name)
    assert len(edges) == 2
    assert ['Y', 'C'] == list(edges.keys())
    assert edges['C'][0] == WIRE_SEGMENT_X


def test_get_incoming_edges(connected_module: Module) -> None:
    with pytest.raises(KeyError):
        connected_module.get_incoming_edges('non_existing')
    inst_and = connected_module.instances['and_inst']
    edges = connected_module.get_incoming_edges(inst_and.name)
    assert len(edges) == 2
    assert ['A', 'B'] == list(edges.keys())
    assert len(edges['A']) == 1
    assert len(edges['B']) == 1
    assert edges['A'][0] == connected_module.wires['in1'][0]
    assert edges['B'][0] == connected_module.wires['in2'][0]

    inst_and.connect('C', None, Dir.IN)
    edges = connected_module.get_incoming_edges(inst_and.name)
    assert len(edges) == 3
    assert ['A', 'B', 'C'] == list(edges.keys())
    assert edges['C'][0] == WIRE_SEGMENT_X


def test_get_instance_from_ps_path(connected_module: Module) -> None:
    and_a_path = PortSegmentPath(raw='test_module1.and_inst.A.0')
    inst = connected_module._get_instance_from_ps_path(and_a_path)
    assert inst == connected_module.instances['and_inst']

    port_path = PortSegmentPath(raw='test_module1.in1.0')
    port = connected_module._get_instance_from_ps_path(port_path)
    assert port == connected_module.ports['in1']

    invalid_path = PortSegmentPath(raw='in1.0')
    invalid = connected_module._get_instance_from_ps_path(invalid_path)
    assert invalid is None


def test_get_wire_ports(connected_module: Module) -> None:
    with pytest.raises(PathResolutionError):
        connected_module.get_wire_ports(ElementPath(raw='test_module1.a.b.c'))

    wire_and = connected_module.wires['wire_and']
    inst_and = connected_module.instances['and_inst']
    inst_xor = connected_module.instances['xor_inst']
    ports = connected_module.get_wire_ports(wire_and[0].path)
    assert len(ports) == 2
    assert f'{inst_and.raw_path}.Y.0' in {p.path.raw for p in ports}
    assert f'{inst_xor.raw_path}.A.0' in {p.path.raw for p in ports}


def test_get_driving_ports(connected_module: Module) -> None:
    with pytest.raises(PathResolutionError):
        connected_module.get_driving_ports(ElementPath(raw='test_module1.a.b.c'))

    wire_and = connected_module.wires['wire_and']
    inst_and = connected_module.instances['and_inst']
    ports = connected_module.get_driving_ports(wire_and[0].path)
    assert len(ports) == 1
    assert f'{inst_and.raw_path}.Y.0' in {p.path.raw for p in ports}


def test_get_load_ports(connected_module: Module) -> None:
    with pytest.raises(PathResolutionError):
        connected_module.get_load_ports(ElementPath(raw='test_module1.a.b.c'))

    wire_and = connected_module.wires['wire_and']
    inst_xor = connected_module.instances['xor_inst']
    ports = connected_module.get_load_ports(wire_and[0].path)
    assert len(ports) == 1
    assert f'{inst_xor.raw_path}.A.0' in {p.path.raw for p in ports}


def test_get_neighbors(connected_module: Module) -> None:
    non_existent = connected_module.get_neighbors('non_existing')
    assert non_existent == {}
    inst_and = connected_module.instances['and_inst']
    neighbors = connected_module.get_neighbors(inst_and.name)
    assert len(neighbors) == 3
    assert ['A', 'B', 'Y'] == list(neighbors.keys())
    assert len(neighbors['A']) == 1
    assert len(neighbors['B']) == 1
    assert len(neighbors['Y']) == 1
    assert neighbors['A'][0] == [connected_module.ports['in1'][0]]
    assert neighbors['B'][0] == [connected_module.ports['in2'][0]]
    assert neighbors['Y'][0] == [connected_module.instances['xor_inst'].ports['A'][0]]

    wseg = connected_module.wires['wire_and'][0]
    pseg = connected_module.instances['or_inst'].ports['A'][0]
    connected_module.disconnect(pseg)
    connected_module.connect(wseg, pseg)
    neighbors = connected_module.get_neighbors(inst_and.name)
    assert len(neighbors) == 3
    assert ['A', 'B', 'Y'] == list(neighbors.keys())
    assert len(neighbors['A']) == 1
    assert len(neighbors['B']) == 1
    assert len(neighbors['Y']) == 1
    assert len(neighbors['A'][0]) == 1
    assert len(neighbors['B'][0]) == 1
    assert len(neighbors['Y'][0]) == 2
    assert neighbors['A'][0] == [connected_module.ports['in1'][0]]
    assert neighbors['B'][0] == [connected_module.ports['in2'][0]]
    assert neighbors['Y'][0] == [connected_module.instances['xor_inst'].ports['A'][0], pseg]

    inst_and.connect('C', None)
    neighbors = connected_module.get_edges(inst_and)
    assert len(neighbors) == 4
    assert ['A', 'B', 'Y', 'C'] == list(neighbors.keys())
    assert neighbors['C'][0] == WIRE_SEGMENT_X


def test_get_succeeding_instances(connected_module: Module) -> None:
    non_existent = connected_module.get_succeeding_instances('non_existing')
    assert non_existent == {}
    inst_and = connected_module.instances['and_inst']
    inst_xor = connected_module.instances['xor_inst']
    inst_not = connected_module.instances['not_inst']
    insts = connected_module.get_succeeding_instances(inst_and.name)
    assert len(insts) == 1
    assert len(insts['Y']) == 1
    assert insts['Y'][0] == [inst_xor]

    wseg = connected_module.wires['wire_and'][0]
    pseg = inst_not.ports['A'][0]
    connected_module.disconnect(pseg)
    connected_module.connect(wseg, pseg)
    insts = connected_module.get_succeeding_instances(inst_and.name)
    assert len(insts) == 1
    assert len(insts['Y']) == 1
    assert insts['Y'][0] == [inst_xor, inst_not]

    insts = connected_module.get_succeeding_instances(inst_not.name)
    assert len(insts) == 1
    assert len(insts['Y']) == 1
    assert insts['Y'][0] == [connected_module.ports['out']]


def test_get_preceeding_instances(connected_module: Module) -> None:
    non_existent = connected_module.get_preceeding_instances('non_existing')
    assert non_existent == {}
    inst_and = connected_module.instances['and_inst']
    inst_xor = connected_module.instances['xor_inst']
    inst_not = connected_module.instances['not_inst']
    insts = connected_module.get_preceeding_instances(inst_and.name)
    assert len(insts) == 2
    assert len(insts['A']) == 1
    assert len(insts['B']) == 1
    assert insts['A'][0] == [connected_module.ports['in1']]
    assert insts['B'][0] == [connected_module.ports['in2']]

    wseg = connected_module.wires['wire_and'][0]
    pseg = inst_not.ports['Y'][0]
    connected_module.disconnect(pseg)
    connected_module.connect(wseg, pseg)
    with pytest.raises(MultipleDriverError):
        connected_module.get_preceeding_instances(inst_xor.name)

    insts = connected_module.get_preceeding_instances(inst_not.name)
    assert len(insts) == 1
    assert len(insts['A']) == 1
    assert insts['A'][0] == [inst_xor]


def test_bfs_paths_between(connected_module: Module) -> None:
    target_connection = set()
    bad_path = ElementPath(raw='a.b.c.d')
    found_connection = connected_module.bfs_paths_between(bad_path, bad_path)
    assert target_connection == found_connection

    out = connected_module.ports['out'][0]
    target_connection = {(out.path,)}
    found_connection = connected_module.bfs_paths_between(out.path, out.path)
    assert target_connection == found_connection

    clk = connected_module.ports['clk'][0]
    out = connected_module.ports['out'][0]
    target_connection = set()
    found_connection = connected_module.bfs_paths_between(clk.path, out.path)
    assert target_connection == found_connection

    in1 = connected_module.ports['in1'][0]
    w1 = connected_module.wires['in1'][0]
    and_a = connected_module.instances['and_inst'].ports['A'][0]
    and_y = connected_module.instances['and_inst'].ports['Y'][0]
    w_and = connected_module.wires['wire_and'][0]
    xor_a = connected_module.instances['xor_inst'].ports['A'][0]
    xor_y = connected_module.instances['xor_inst'].ports['Y'][0]
    w_xor = connected_module.wires['wire_xor'][0]
    not_a = connected_module.instances['not_inst'].ports['A'][0]
    not_y = connected_module.instances['not_inst'].ports['Y'][0]
    w_out = connected_module.wires['out'][0]
    out = connected_module.ports['out'][0]
    target_connection = {
        (in1.path, w1.path, and_a.path, and_y.path, w_and.path, xor_a.path, xor_y.path, w_xor.path, not_a.path, not_y.path, w_out.path, out.path)
    }
    found_connection = connected_module.bfs_paths_between(in1.path, out.path)
    assert target_connection == found_connection

    target_connection = set()
    found_connection = connected_module.bfs_paths_between(out.path, in1.path)
    assert target_connection == found_connection


def test_bfs_paths_between_feedback_loop(connected_module: Module) -> None:
    xor_b = connected_module.instances['xor_inst'].ports['B'][0]
    w_out = connected_module.wires['out_ff'][0]

    connected_module.disconnect(xor_b)
    connected_module.connect(w_out, xor_b)
    assert xor_b in w_out.port_segments
    assert xor_b.ws_path == w_out.path

    in1 = connected_module.ports['in1'][0]
    w1 = connected_module.wires['in1'][0]
    and_a = connected_module.instances['and_inst'].ports['A'][0]
    and_y = connected_module.instances['and_inst'].ports['Y'][0]
    w_and = connected_module.wires['wire_and'][0]
    xor_a = connected_module.instances['xor_inst'].ports['A'][0]
    xor_y = connected_module.instances['xor_inst'].ports['Y'][0]
    w_xor = connected_module.wires['wire_xor'][0]
    dff_d = connected_module.instances['dff_inst'].ports['D'][0]
    dff_q = connected_module.instances['dff_inst'].ports['Q'][0]
    out = connected_module.ports['out_ff'][0]
    target_connection = {
        (in1.path, w1.path, and_a.path, and_y.path, w_and.path, xor_a.path, xor_y.path, w_xor.path, dff_d.path, dff_q.path, w_out.path, out.path)
    }
    found_connection = connected_module.bfs_paths_between(in1.path, out.path)
    assert target_connection == found_connection


def test_bfs_paths_between_multipaths(connected_module: Module) -> None:
    and_b = connected_module.instances['and_inst'].ports['B'][0]
    w1 = connected_module.wires['in1'][0]
    connected_module.disconnect(and_b)
    connected_module.connect(w1, and_b)
    assert and_b in w1.port_segments
    assert and_b.ws_path == w1.path

    in1 = connected_module.ports['in1'][0]
    and_a = connected_module.instances['and_inst'].ports['A'][0]
    and_y = connected_module.instances['and_inst'].ports['Y'][0]
    w_and = connected_module.wires['wire_and'][0]
    xor_a = connected_module.instances['xor_inst'].ports['A'][0]
    xor_y = connected_module.instances['xor_inst'].ports['Y'][0]
    w_xor = connected_module.wires['wire_xor'][0]
    not_a = connected_module.instances['not_inst'].ports['A'][0]
    not_y = connected_module.instances['not_inst'].ports['Y'][0]
    w_out = connected_module.wires['out'][0]
    out = connected_module.ports['out'][0]
    target_connection = {
        (in1.path, w1.path, and_a.path, and_y.path, w_and.path, xor_a.path, xor_y.path, w_xor.path, not_a.path, not_y.path, w_out.path, out.path),
        (in1.path, w1.path, and_b.path, and_y.path, w_and.path, xor_a.path, xor_y.path, w_xor.path, not_a.path, not_y.path, w_out.path, out.path),
    }
    found_connection = connected_module.bfs_paths_between(in1.path, out.path, return_first_only=False)
    assert target_connection == found_connection


def test_bfs_path_postprocess_invalid(connected_module: Module) -> None:
    path_post_process = connected_module._bfs_path_postprocess([], None)
    assert path_post_process == {0} - {0}  # Funny eyes <=> empty set


def test_dfs_paths_between(connected_module: Module) -> None:
    target_connection = set()
    bad_path = ElementPath(raw='a.b.c.d')
    found_connection = connected_module.dfs_paths_between(bad_path, bad_path)
    assert target_connection == found_connection

    out = connected_module.ports['out'][0]
    target_connection = {(out.path,)}
    found_connection = connected_module.dfs_paths_between(out.path, out.path)
    assert target_connection == found_connection

    clk = connected_module.ports['clk'][0]
    out = connected_module.ports['out'][0]
    target_connection = set()
    found_connection = connected_module.dfs_paths_between(clk.path, out.path)
    assert target_connection == found_connection

    in1 = connected_module.ports['in1'][0]
    w1 = connected_module.wires['in1'][0]
    and_a = connected_module.instances['and_inst'].ports['A'][0]
    and_y = connected_module.instances['and_inst'].ports['Y'][0]
    w_and = connected_module.wires['wire_and'][0]
    xor_a = connected_module.instances['xor_inst'].ports['A'][0]
    xor_y = connected_module.instances['xor_inst'].ports['Y'][0]
    w_xor = connected_module.wires['wire_xor'][0]
    not_a = connected_module.instances['not_inst'].ports['A'][0]
    not_y = connected_module.instances['not_inst'].ports['Y'][0]
    w_out = connected_module.wires['out'][0]
    out = connected_module.ports['out'][0]
    target_connection = {
        (in1.path, w1.path, and_a.path, and_y.path, w_and.path, xor_a.path, xor_y.path, w_xor.path, not_a.path, not_y.path, w_out.path, out.path)
    }
    found_connection = connected_module.dfs_paths_between(in1.path, out.path)
    assert target_connection == found_connection

    target_connection = set()
    found_connection = connected_module.dfs_paths_between(out.path, in1.path)
    assert target_connection == found_connection


def test_dfs_paths_between_feedback_loop(connected_module: Module) -> None:
    xor_b = connected_module.instances['xor_inst'].ports['B'][0]
    w_out = connected_module.wires['out_ff'][0]

    connected_module.disconnect(xor_b)
    connected_module.connect(w_out, xor_b)
    assert xor_b in w_out.port_segments
    assert xor_b.ws_path == w_out.path

    in1 = connected_module.ports['in1'][0]
    w1 = connected_module.wires['in1'][0]
    and_a = connected_module.instances['and_inst'].ports['A'][0]
    and_y = connected_module.instances['and_inst'].ports['Y'][0]
    w_and = connected_module.wires['wire_and'][0]
    xor_a = connected_module.instances['xor_inst'].ports['A'][0]
    xor_y = connected_module.instances['xor_inst'].ports['Y'][0]
    w_xor = connected_module.wires['wire_xor'][0]
    dff_d = connected_module.instances['dff_inst'].ports['D'][0]
    dff_q = connected_module.instances['dff_inst'].ports['Q'][0]
    out = connected_module.ports['out_ff'][0]
    target_connection = {
        (in1.path, w1.path, and_a.path, and_y.path, w_and.path, xor_a.path, xor_y.path, w_xor.path, dff_d.path, dff_q.path, w_out.path, out.path)
    }
    found_connection = connected_module.dfs_paths_between(in1.path, out.path)
    assert target_connection == found_connection


def test_dfs_paths_between_multipaths(connected_module: Module) -> None:
    and_b = connected_module.instances['and_inst'].ports['B'][0]
    w1 = connected_module.wires['in1'][0]
    connected_module.disconnect(and_b)
    connected_module.connect(w1, and_b)
    assert and_b in w1.port_segments
    assert and_b.ws_path == w1.path

    in1 = connected_module.ports['in1'][0]
    and_a = connected_module.instances['and_inst'].ports['A'][0]
    and_y = connected_module.instances['and_inst'].ports['Y'][0]
    w_and = connected_module.wires['wire_and'][0]
    xor_a = connected_module.instances['xor_inst'].ports['A'][0]
    xor_y = connected_module.instances['xor_inst'].ports['Y'][0]
    w_xor = connected_module.wires['wire_xor'][0]
    not_a = connected_module.instances['not_inst'].ports['A'][0]
    not_y = connected_module.instances['not_inst'].ports['Y'][0]
    w_out = connected_module.wires['out'][0]
    out = connected_module.ports['out'][0]
    target_connection = {
        (in1.path, w1.path, and_a.path, and_y.path, w_and.path, xor_a.path, xor_y.path, w_xor.path, not_a.path, not_y.path, w_out.path, out.path),
        (in1.path, w1.path, and_b.path, and_y.path, w_and.path, xor_a.path, xor_y.path, w_xor.path, not_a.path, not_y.path, w_out.path, out.path),
    }
    found_connection = connected_module.dfs_paths_between(in1.path, out.path, max_paths=-1)
    assert target_connection == found_connection


def test_split_instance(dff_module: Module) -> None:
    with pytest.raises(ObjectNotFoundError):
        dff_module.split('abc')

    assert len(dff_module.instances) == 1
    assert len(dff_module.instances_by_types['§dff']) == 1
    dff = dff_module.instances_by_types['§dff'][0]
    dff.parameters['CLK_POLARITY'] = Signal.LOW
    connections = dff.connections
    dffs = dff_module.split(dff)
    assert dff.name not in dff_module.instances
    assert len(dffs) == 4
    for idx, inst in dffs.items():
        assert inst.name in dff_module.instances
        assert inst.width == 1
        assert inst.ports['D'].width == 1
        assert inst.ports['CLK'].width == 1
        assert inst.ports['Q'].width == 1
        assert inst.ports['D'][0].ws_path == connections['D'][idx]
        assert inst.ports['CLK'][0].ws_path == connections['CLK'][0]
        assert inst.ports['Q'][0].ws_path == connections['Q'][idx]
        assert inst.parameters['WIDTH'] == 1
        assert inst.parameters['CLK_POLARITY'] == dff.parameters['CLK_POLARITY']


def test_split_all(dff_module: Module) -> None:
    splits = dff_module.split_all('abc')
    assert splits == 0

    splits = dff_module.split_all('dff', fuzzy=False)
    assert splits == 0

    splits = dff_module.split_all('dff')
    assert splits == 1

    c = Circuit(name='c')
    c.add_module(dff_module)
    subm = c.create_module('sub')
    D = subm.create_port('D', Dir.IN, width=8)
    adff(subm, 'dff_inst', D=D)
    dff_module.create_instance(subm, 'subm_inst')
    splits = dff_module.split_all('dff')
    assert splits == 0
    assert len(subm.instances) == 1
    splits = dff_module.split_all('dff', recursive=True)
    assert splits == 1
    assert len(subm.instances) == 8


def test_split_all_empty(dff_module: Module) -> None:
    splits = dff_module.split_all(fuzzy=False)
    assert splits == 0

    splits = dff_module.split_all()
    assert splits == 1


def test_make_chain(dff_module: Module) -> None:
    with pytest.raises(ValueError):
        dff_module.make_chain([], 'foo', 'bar')

    dff_module.split_all('dff')
    dffs = dff_module.get_instances(type='dff', fuzzy=True)
    assert len(dffs) == 4

    for dff in dffs:
        dff.disconnect('D')
        dff.disconnect('Q')
    ports = dff_module.make_chain(dffs, 'D', 'Q')
    assert ports[0] == dffs[0].ports['D']
    assert ports[1] == dffs[-1].ports['Q']
    for idx in range(len(dffs) - 1):
        assert dffs[idx].ports['Q'].connected_wires == dffs[idx + 1].ports['D'].connected_wires


def test_flatten(dff_circuit: Circuit) -> None:
    from utils import save_results

    from netlist_carpentry.io.write.py2v import P2VTransformer as P2V

    m2 = dff_circuit['M2']
    m21 = dff_circuit['M21']
    assert len(m2.submodules) == 2
    assert m2.instances['m21'] in m2.submodules
    assert m2.instances['m22'] in m2.submodules

    dff = m21.instances_by_types['§dff'][0]
    m21_inst = m2.instances['m21']
    m21_conn = m21_inst.connections
    m2.flatten(skip_name=['m22'])
    save_results(P2V().module2v(m2), 'v')
    assert len(m2.submodules) == 1
    assert f'm21_{dff.name}' in m2.instances
    dff_m2 = m2.instances[f'm21_{dff.name}']
    assert dff_m2.ports['D'][0].raw_ws_path == m21_conn['A'][0].raw
    assert dff_m2.ports['Q'][0].raw_ws_path == m21_conn['Y'][0].raw
    assert dff_m2.ports['CLK'][0].raw_ws_path == m21_conn['CLK'][0].raw


def test_flatten_recursive(dff_circuit: Circuit) -> None:
    from utils import save_results

    from netlist_carpentry.io.write.py2v import P2VTransformer as P2V

    top = dff_circuit.top
    dffs = len(top.get_instances(type='dff', fuzzy=True, recursive=True))
    top.flatten(recursive=True)
    save_results(P2V().module2v(top), 'v')
    assert len(top.submodules) == 0
    assert len(top.get_instances(type='dff', fuzzy=True)) == dffs


def test_optimize(connected_module: Module) -> None:
    assert len(connected_module.wires) == 12
    assert len(connected_module.instances) == 5
    any_removed = connected_module.optimize()  # Removes unused wire "en"
    assert any_removed
    assert len(connected_module.wires) == 11
    assert len(connected_module.instances) == 5

    any_removed = connected_module.optimize()  # Nothing removed
    assert not any_removed
    assert len(connected_module.wires) == 11
    assert len(connected_module.instances) == 5

    connected_module.disconnect(connected_module.ports['out'][0])
    any_removed = connected_module.optimize()  # Removes now unused wire "out" and instance
    assert any_removed
    assert len(connected_module.wires) == 10
    assert len(connected_module.instances) == 4

    connected_module.disconnect(connected_module.ports['out_ff'][0])
    any_removed = connected_module.optimize()  # Removes now unused wire "out_ff" and all connected instances
    assert any_removed
    assert len(connected_module.wires) == 0
    assert len(connected_module.instances) == 0


def test_set_name(connected_module: Module) -> None:
    connected_module.set_name('SOME_MODULE')
    assert connected_module.name == 'SOME_MODULE'
    for p in connected_module.ports.values():
        assert p.path[0] == 'SOME_MODULE'
        for _, ps in p:
            assert ps.path[0] == 'SOME_MODULE'
    for w in connected_module.wires.values():
        assert w.path[0] == 'SOME_MODULE'
        for _, ws in w:
            assert ws.path[0] == 'SOME_MODULE'
            for ps in ws.port_segments:
                assert ps.path[0] == 'SOME_MODULE'
    for i in connected_module.instances.values():
        assert i.path[0] == 'SOME_MODULE'
        for p in i.ports.values():
            assert p.path[0] == 'SOME_MODULE'
            for _, s in p:
                assert s.path[0] == 'SOME_MODULE'
                if not s.is_tied:
                    assert s.ws_path[0] == 'SOME_MODULE'

    connected_module.set_name('SOME_MODULE')
    assert connected_module.name == 'SOME_MODULE'


def test_change_mutability(standard_module: Module) -> None:
    assert not standard_module.locked
    standard_module.change_mutability(is_now_locked=True)
    assert standard_module.locked
    assert not standard_module.ports['test_port'].locked
    assert not standard_module.wires['test_wire'].locked
    assert not standard_module.get_instance('test_instance').locked

    standard_module.change_mutability(is_now_locked=True, recursive=True)
    assert standard_module.locked
    assert standard_module.ports['test_port'].locked
    assert standard_module.wires['test_wire'].locked
    assert standard_module.get_instance('test_instance').locked


def test_evaluate(connected_module: Module) -> None:
    connected_module.evaluate()
    for p in connected_module.output_ports:
        assert p.signal == Signal.UNDEFINED

    and_inst = connected_module.get_instance('and_inst')
    or_inst = connected_module.get_instance('or_inst')
    xor_inst = connected_module.get_instance('xor_inst')
    not_inst = connected_module.get_instance('not_inst')
    dff_inst = connected_module.get_instance('dff_inst')

    connected_module.ports['in1'].set_signal(Signal.LOW)
    connected_module.ports['in2'].set_signal(Signal.LOW)
    connected_module.ports['in3'].set_signal(Signal.LOW)
    connected_module.ports['in4'].set_signal(Signal.HIGH)
    connected_module.evaluate()

    assert connected_module.wires['in1'].signal_array[0] == Signal.LOW
    assert connected_module.wires['in2'].signal_array[0] == Signal.LOW
    assert connected_module.wires['in3'].signal_array[0] == Signal.LOW
    assert connected_module.wires['in4'].signal_array[0] == Signal.HIGH
    assert and_inst.ports['A'].signal == Signal.LOW
    assert and_inst.ports['B'].signal == Signal.LOW
    assert and_inst.ports['Y'].signal == Signal.LOW
    assert connected_module.wires['wire_and'].signal_array[0] == Signal.LOW  # 0 AND 0 -> 0
    assert or_inst.ports['A'].signal == Signal.LOW
    assert or_inst.ports['B'].signal == Signal.HIGH
    assert or_inst.ports['Y'].signal == Signal.HIGH
    assert connected_module.wires['wire_or'].signal_array[0] == Signal.HIGH  # 0 OR 1 -> 1
    assert xor_inst.ports['A'].signal == Signal.LOW
    assert xor_inst.ports['B'].signal == Signal.HIGH
    assert xor_inst.ports['Y'].signal == Signal.HIGH
    assert connected_module.wires['wire_xor'].signal_array[0] == Signal.HIGH  # 0 XOR 1 -> 1
    assert not_inst.ports['A'].signal == Signal.HIGH
    assert not_inst.ports['Y'].signal == Signal.LOW
    assert connected_module.wires['out'].signal_array[0] == Signal.LOW  # NOT 1 -> 0
    assert connected_module.ports['out'].signal == Signal.LOW

    # Inactive part
    assert dff_inst.ports['CLK'].signal == Signal.UNDEFINED
    assert dff_inst.ports['RST'].signal == Signal.UNDEFINED
    assert dff_inst.ports['D'].signal == Signal.HIGH
    assert dff_inst.ports['EN'].signal == Signal.HIGH
    assert dff_inst.ports['Q'].signal == Signal.UNDEFINED
    assert connected_module.ports['out_ff'].signal == Signal.UNDEFINED

    # Now reset ff
    connected_module.ports['rst'].set_signal(Signal.LOW)
    connected_module.evaluate()
    assert dff_inst.ports['CLK'].signal == Signal.UNDEFINED
    assert dff_inst.ports['RST'].signal == Signal.LOW
    assert dff_inst.ports['D'].signal == Signal.HIGH
    assert dff_inst.ports['Q'].signal == Signal.LOW
    assert connected_module.ports['out_ff'].signal == Signal.LOW

    connected_module.ports['rst'].set_signal(Signal.HIGH)
    connected_module.evaluate()
    assert dff_inst.ports['CLK'].signal == Signal.UNDEFINED
    assert dff_inst.ports['RST'].signal == Signal.HIGH
    assert dff_inst.ports['D'].signal == Signal.HIGH
    assert dff_inst.ports['Q'].signal == Signal.LOW
    assert connected_module.ports['out_ff'].signal == Signal.LOW

    # Now clk cycle
    # Now reset ff
    connected_module.ports['clk'].set_signal(Signal.LOW)
    connected_module.evaluate()
    assert dff_inst.ports['CLK'].signal == Signal.LOW
    assert dff_inst.ports['RST'].signal == Signal.HIGH
    assert dff_inst.ports['D'].signal == Signal.HIGH
    assert dff_inst.ports['Q'].signal == Signal.LOW
    assert connected_module.ports['out_ff'].signal == Signal.LOW

    connected_module.ports['clk'].set_signal(Signal.HIGH)
    connected_module.evaluate()
    assert dff_inst.ports['CLK'].signal == Signal.HIGH
    assert dff_inst.ports['RST'].signal == Signal.HIGH
    assert dff_inst.ports['D'].signal == Signal.HIGH
    assert dff_inst.ports['Q'].signal == Signal.HIGH
    assert connected_module.ports['out_ff'].signal == Signal.HIGH


def test_evaluate_corner_cases(standard_module: Module) -> None:
    with pytest.raises(EvaluationError):
        # Add dummy instance without evaluate method
        inst = Instance(raw_path='test_module1.test', instance_type='LOL', module=None)
        standard_module.add_instance(inst)
        inst.connect('A', WireSegmentPath(raw='test_module1.test_wire.0'), direction=Dir.IN)
        wseg = standard_module.wires['test_wire'][0]
        pseg = inst.ports['A'][0]
        standard_module.disconnect(pseg)
        standard_module.connect(wseg, pseg)
        standard_module.evaluate()


def test_build_graph(connected_module: Module) -> None:
    g = connected_module.graph()

    assert isinstance(g, ModuleGraph)
    assert len(g.edges) == 4 + 8  # 4 FF-related edges (in/out) and 8 combinational edges (in/out)
    # Module Ports - number of outgoing edges
    assert len(g.edges('in1')) == 1
    assert len(g.edges('in2')) == 1
    assert len(g.edges('in3')) == 1
    assert len(g.edges('in4')) == 1
    assert len(g.edges('clk')) == 1
    assert len(g.edges('rst')) == 1
    assert len(g.edges('out')) == 0
    assert len(g.edges('out_ff')) == 0

    # Module Ports - number of incoming edges
    assert len(g.in_edges('in1')) == 0
    assert len(g.in_edges('in2')) == 0
    assert len(g.in_edges('in3')) == 0
    assert len(g.in_edges('in4')) == 0
    assert len(g.in_edges('clk')) == 0
    assert len(g.in_edges('rst')) == 0
    assert len(g.in_edges('out')) == 1
    assert len(g.in_edges('out_ff')) == 1

    # Instance edges outgoing
    assert len(g.edges('and_inst')) == 1
    assert len(g.edges('or_inst')) == 1
    assert len(g.edges('xor_inst')) == 2
    assert len(g.edges('not_inst')) == 1
    assert len(g.edges('dff_inst')) == 1

    # Instance edges incoming
    assert len(g.in_edges('and_inst')) == 2
    assert len(g.in_edges('or_inst')) == 2
    assert len(g.in_edges('xor_inst')) == 2
    assert len(g.in_edges('not_inst')) == 1
    assert len(g.in_edges('dff_inst')) == 3

    # Edge connections - combinational
    assert g.edges['in1', 'and_inst', 'in1§A'] == {'ename': 'in1', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['in2', 'and_inst', 'in2§B'] == {'ename': 'in2', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['in3', 'or_inst', 'in3§A'] == {'ename': 'in3', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['in4', 'or_inst', 'in4§B'] == {'ename': 'in4', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['and_inst', 'xor_inst', 'Y§A'] == {'ename': 'wire_and', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['or_inst', 'xor_inst', 'Y§B'] == {'ename': 'wire_or', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['xor_inst', 'not_inst', 'Y§A'] == {'ename': 'wire_xor', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['not_inst', 'out', 'Y§out'] == {'ename': 'out', 'dr_seg': 0, 'ld_seg': 0}

    # Edge connections - sequential
    assert g.edges['xor_inst', 'dff_inst', 'Y§D'] == {'ename': 'wire_xor', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['clk', 'dff_inst', 'clk§CLK'] == {'ename': 'clk', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['rst', 'dff_inst', 'rst§RST'] == {'ename': 'rst', 'dr_seg': 0, 'ld_seg': 0}
    assert g.edges['dff_inst', 'out_ff', 'Q§out_ff'] == {'ename': 'out_ff', 'dr_seg': 0, 'ld_seg': 0}

    # Nodes
    assert len(g.nodes) == 5 + 8  # 5 instances + 8 in/out ports
    # Instance nodes
    assert g.nodes['and_inst']['ndata'] == connected_module.get_instance('and_inst')
    assert g.nodes['or_inst']['ndata'] == connected_module.get_instance('or_inst')
    assert g.nodes['xor_inst']['ndata'] == connected_module.get_instance('xor_inst')
    assert g.nodes['not_inst']['ndata'] == connected_module.get_instance('not_inst')
    assert g.nodes['dff_inst']['ndata'] == connected_module.get_instance('dff_inst')
    # Port nodes
    assert g.nodes['in1']['ndata'] == connected_module.get_port('in1')
    assert g.nodes['in2']['ndata'] == connected_module.get_port('in2')
    assert g.nodes['in3']['ndata'] == connected_module.get_port('in3')
    assert g.nodes['in4']['ndata'] == connected_module.get_port('in4')
    assert g.nodes['clk']['ndata'] == connected_module.get_port('clk')
    assert g.nodes['rst']['ndata'] == connected_module.get_port('rst')
    assert g.nodes['out']['ndata'] == connected_module.get_port('out')
    assert g.nodes['out_ff']['ndata'] == connected_module.get_port('out_ff')

    # Instance node types
    assert g.nodes['and_inst']['nsubtype'] == '§and'
    assert g.nodes['or_inst']['nsubtype'] == '§or'
    assert g.nodes['xor_inst']['nsubtype'] == '§xor'
    assert g.nodes['not_inst']['nsubtype'] == '§not'
    assert g.nodes['dff_inst']['nsubtype'] == '§adffe'
    # Port node types
    assert g.nodes['in1']['nsubtype'] == 'input'
    assert g.nodes['in2']['nsubtype'] == 'input'
    assert g.nodes['in3']['nsubtype'] == 'input'
    assert g.nodes['in4']['nsubtype'] == 'input'
    assert g.nodes['clk']['nsubtype'] == 'input'
    assert g.nodes['rst']['nsubtype'] == 'input'
    assert g.nodes['out']['nsubtype'] == 'output'
    assert g.nodes['out_ff']['nsubtype'] == 'output'


def test_graph_property(connected_module: Module) -> None:
    g = connected_module.graph()
    g1 = copy.deepcopy(g)
    assert tuple(g1.nodes) == tuple(g.nodes)
    assert tuple(g1.nodes) == tuple(g.nodes)

    connected_module.remove_port('out_ff')
    g2 = copy.deepcopy(connected_module.graph())
    assert tuple(g1.nodes) != tuple(g2.nodes)
    assert tuple(g2.nodes) == tuple(connected_module.graph().nodes)


def test_show_interactive(dff_module: Module) -> None:
    dash = dff_module.show(interactive=True)
    children = dash.layout.children
    assert len(children) == 3
    assert children[0].id == 'clicked-nodes-store'
    assert children[1].id == 'clicked-edges-store'
    assert children[2].children[0].id == 'circuit-graph'
    assert children[2].children[0].elements == [
        {'data': {'id': 'dff_inst', 'label': 'dff_inst', 'object_type': 'INSTANCE', 'object_subtype': '§dff'}},
        {'data': {'id': 'D', 'label': 'D', 'object_type': 'PORT', 'object_subtype': 'input'}},
        {'data': {'id': 'CLK', 'label': 'CLK', 'object_type': 'PORT', 'object_subtype': 'input'}},
        {'data': {'id': 'Q', 'label': 'Q', 'object_type': 'PORT', 'object_subtype': 'output'}},
        {'data': {'label': 'Q->Q', 'source': 'dff_inst', 'target': 'Q'}},
        {'data': {'label': 'D->D', 'source': 'D', 'target': 'dff_inst'}},
        {'data': {'label': 'CLK->CLK', 'source': 'CLK', 'target': 'dff_inst'}},
    ]
    assert children[2].children[0].layout == {'name': 'klay', 'directed': True}
    assert children[2].children[0].style == {'width': '100%', 'height': '550px', 'background-color': 'black'}

    dash = dff_module.show(interactive=True, style={'abc': 'def', 'foo': 'bar'})
    assert dash.layout.children[2].children[0].style == {'abc': 'def', 'foo': 'bar'}
    assert children[2].children[1].id == 'cytoscape-mouseoverNodeData-output'
    assert children[2].children[2].id == 'cytoscape-mouseoverEdgeData-output'


def test_show_static(dff_module: Module) -> None:
    if os.path.exists('tests/files/gen/module_vis.svg'):
        os.remove('tests/files/gen/module_vis.svg')
    dff_module.show(figpath='tests/files/gen/module_vis.svg')
    assert os.path.exists('tests/files/gen/module_vis.svg')


def test_normalize_metadata(standard_module: Module) -> None:
    found = standard_module.normalize_metadata()
    assert found == {}
    found = standard_module.normalize_metadata(include_empty=True)
    target: METADATA_DICT = {
        'test_module1': {},
        'test_module1.test_instance': {},
        'test_module1.test_instance.A': {},
        'test_module1.test_instance.A.0': {},
        'test_module1.test_instance.B': {},
        'test_module1.test_instance.B.0': {},
        'test_module1.test_instance.Y': {},
        'test_module1.test_instance.Y.0': {},
        'test_module1.test_port': {},
        'test_module1.test_port.0': {},
        'test_module1.test_wire': {},
        'test_module1.test_wire.0': {},
    }
    assert found == target
    standard_module.metadata.set('foo', 'bar')
    standard_module.metadata.set('foo', 'baz', 'cat')
    standard_module.ports['test_port'][0].metadata.set('foo', 'bar')
    standard_module.wires['test_wire'].metadata.set('foo', 'baz', 'cat')
    found2 = standard_module.normalize_metadata()
    target2: METADATA_DICT = {
        'test_module1': {'general': {'foo': 'bar'}, 'cat': {'foo': 'baz'}},
        'test_module1.test_port.0': {'general': {'foo': 'bar'}},
        'test_module1.test_wire': {'cat': {'foo': 'baz'}},
    }
    assert found2 == target2
    found3 = standard_module.normalize_metadata(sort_by='category')
    target3: METADATA_DICT = {
        'general': {
            'test_module1': {'foo': 'bar'},
            'test_module1.test_port.0': {'foo': 'bar'},
        },
        'cat': {
            'test_module1': {'foo': 'baz'},
            'test_module1.test_wire': {'foo': 'baz'},
        },
    }
    assert found3 == target3

    # Checks if {"foo": "bar"} is part of val
    found4 = standard_module.normalize_metadata(sort_by='category', filter=lambda cat, md: 'foo' in md and md['foo'] == 'bar')
    target4: METADATA_DICT = {'general': {'test_module1': {'foo': 'bar'}, 'test_module1.test_port.0': {'foo': 'bar'}}}
    assert found4 == target4

    # Illegal operation should be resolved to False
    found5 = standard_module.normalize_metadata(sort_by='category', filter=lambda cat, md: md.is_integer())
    assert found5 == {}


def test_export_metadata(standard_module: Module) -> None:
    path = 'tests/files/gen/module_md.json'
    if os.path.exists(path):
        os.remove(path)
    standard_module.export_metadata(path, include_empty=True)
    assert os.path.exists(path)
    with open(path) as f:
        found_data = json.loads(f.read())

    target_data: METADATA_DICT = {
        'test_module1': {},
        'test_module1.test_instance': {},
        'test_module1.test_instance.A': {},
        'test_module1.test_instance.A.0': {},
        'test_module1.test_instance.B': {},
        'test_module1.test_instance.B.0': {},
        'test_module1.test_instance.Y': {},
        'test_module1.test_instance.Y.0': {},
        'test_module1.test_port': {},
        'test_module1.test_port.0': {},
        'test_module1.test_wire': {},
        'test_module1.test_wire.0': {},
    }
    assert target_data == found_data
    os.remove(path)
    standard_module.metadata.set('foo', 'bar')
    standard_module.metadata.set('foo', 'baz', 'cat')
    standard_module.ports['test_port'][0].metadata.set('foo', 'bar')
    standard_module.wires['test_wire'].metadata.set('foo', 'baz', 'cat')
    standard_module.export_metadata(path)
    target_data2: METADATA_DICT = {
        'test_module1': {'general': {'foo': 'bar'}, 'cat': {'foo': 'baz'}},
        'test_module1.test_port.0': {'general': {'foo': 'bar'}},
        'test_module1.test_wire': {'cat': {'foo': 'baz'}},
    }
    with open(path) as f:
        found_data2 = json.loads(f.read())
    assert found_data2 == target_data2

    standard_module.export_metadata(Path(path), sort_by='category')
    target_data3: METADATA_DICT = {
        'general': {
            'test_module1': {'foo': 'bar'},
            'test_module1.test_port.0': {'foo': 'bar'},
        },
        'cat': {
            'test_module1': {'foo': 'baz'},
            'test_module1.test_wire': {'foo': 'baz'},
        },
    }
    with open(path) as f:
        found_data3 = json.loads(f.read())
    assert found_data3 == target_data3
    os.remove(path)

    standard_module.export_metadata(path, sort_by='category', filter=lambda cat, md: 'foo' in md and md['foo'] == 'bar')
    target_data4: METADATA_DICT = {'general': {'test_module1': {'foo': 'bar'}, 'test_module1.test_port.0': {'foo': 'bar'}}}
    with open(path) as f:
        found_data4 = json.loads(f.read())
    assert found_data4 == target_data4
    os.remove(path)


def test_module_str(empty_module: Module) -> None:
    # Test the string representation of a module
    assert str(empty_module) == 'Module "test_module1"'


def test_module_repr(empty_module: Module) -> None:
    # Test the representation of a module
    assert repr(empty_module) == 'Module(test_module1)'


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name, '-vv'])
