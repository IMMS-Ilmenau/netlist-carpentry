import copy
import os

import pytest

from netlist_carpentry import WIRE_SEGMENT_1, WIRE_SEGMENT_X
from netlist_carpentry.core.exceptions import (
    IdentifierConflictError,
    InvalidPortDirectionError,
    InvalidSignalError,
    ObjectLockedError,
    ObjectNotFoundError,
    ParentNotFoundError,
)
from netlist_carpentry.core.netlist_elements.element_path import ElementPath as ElementPath
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.element_type import EType
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT
from netlist_carpentry.core.netlist_elements.netlist_element import NetlistElement
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.signal import Signal


@pytest.fixture
def empty_standard_instance() -> Instance:
    return Instance(raw_path='test_module1.test_instance1', instance_type='test_instance_type', is_primitive=True, module=None)


@pytest.fixture
def standard_instance_with_ports() -> Instance:
    from utils import standard_instance_with_ports as siwp

    return siwp()


@pytest.fixture
def locked_instance() -> Instance:
    from utils import locked_instance as ii

    return ii()


def test_instance_creation(empty_standard_instance: Instance) -> None:
    assert empty_standard_instance.name == 'test_instance1'
    assert empty_standard_instance.path.name == 'test_instance1'
    assert empty_standard_instance.path.type is EType.INSTANCE
    assert empty_standard_instance.path.raw == 'test_module1.test_instance1'
    assert empty_standard_instance.instance_type == 'test_instance_type'
    assert empty_standard_instance.is_primitive is True
    assert empty_standard_instance.type is EType.INSTANCE
    assert empty_standard_instance.is_module_instance is False
    assert empty_standard_instance.connections == {}  # Ports are not set in default instance
    assert empty_standard_instance.ports == {}

    assert not empty_standard_instance.can_carry_signal


def test_instance_with_ports(standard_instance_with_ports: Instance) -> None:
    assert len(standard_instance_with_ports.connections) == 3
    assert standard_instance_with_ports.connections['PortA'][0].name == '1'
    assert standard_instance_with_ports.connections['PortB'][0].name == '2'
    assert standard_instance_with_ports.connections['PortB'][1].name == '3'
    assert standard_instance_with_ports.connections['PortB'][2].name == '2'
    assert standard_instance_with_ports.connections['PortB'][3].name == '1'
    assert standard_instance_with_ports.connections['PortC'][0].name == '4'

    assert standard_instance_with_ports.connection_str_paths['PortA'][0] == 'test_module1.wire4b.1'
    assert standard_instance_with_ports.connection_str_paths['PortB'][0] == 'test_module1.wire4b.2'
    assert standard_instance_with_ports.connection_str_paths['PortB'][1] == 'test_module1.wire4b.3'
    assert standard_instance_with_ports.connection_str_paths['PortB'][2] == 'test_module1.wire4b.2'
    assert standard_instance_with_ports.connection_str_paths['PortB'][3] == 'test_module1.wire4b.1'
    assert standard_instance_with_ports.connection_str_paths['PortC'][0] == 'test_module1.wire4b.4'

    assert len(standard_instance_with_ports.ports) == 3
    assert standard_instance_with_ports.ports['PortA'].name == 'PortA'
    assert standard_instance_with_ports.ports['PortA'].direction == PortDirection.IN
    assert standard_instance_with_ports.ports['PortA'].is_instance_port
    assert standard_instance_with_ports.ports['PortA'].width == 1
    assert standard_instance_with_ports.ports['PortA'].signal == Signal.UNDEFINED  # Load connected -> UNDEFINED until evaluation
    standard_instance_with_ports.ports['PortA'][0].set_ws_path('')
    assert standard_instance_with_ports.ports['PortA'].signal == Signal.FLOATING  # Load unconnected -> Signal.FLOATING
    assert standard_instance_with_ports.ports['PortB'].name == 'PortB'
    assert standard_instance_with_ports.ports['PortB'].direction == PortDirection.IN
    assert standard_instance_with_ports.ports['PortB'].is_instance_port
    assert standard_instance_with_ports.ports['PortB'].width == 4
    assert standard_instance_with_ports.ports['PortB'][0].signal == Signal.UNDEFINED  # Load connected -> UNDEFINED until evaluation
    standard_instance_with_ports.ports['PortB'][0].set_ws_path('')
    assert standard_instance_with_ports.ports['PortB'][0].signal == Signal.FLOATING  # Load unconnected -> Signal.FLOATING
    assert standard_instance_with_ports.ports['PortC'].name == 'PortC'
    assert standard_instance_with_ports.ports['PortC'].direction == PortDirection.OUT
    assert standard_instance_with_ports.ports['PortC'].is_instance_port
    assert standard_instance_with_ports.ports['PortC'].width == 1
    assert standard_instance_with_ports.ports['PortC'].signal == Signal.UNDEFINED
    standard_instance_with_ports.ports['PortC'][0].set_ws_path('')
    assert standard_instance_with_ports.ports['PortC'].signal == Signal.UNDEFINED  # Driver unconnected -> UNDEFINED until evaluation

    assert not standard_instance_with_ports.can_carry_signal


def test_wire_parent_init() -> None:
    with pytest.raises(TypeError):
        Instance(raw_path='a.b.c', instance_type='foo', module=NetlistElement(raw_path='a.b'))


def test_parent(standard_instance_with_ports: Instance) -> None:
    from utils import empty_module

    m = empty_module()
    standard_instance_with_ports.module = m
    parent = standard_instance_with_ports.parent
    assert parent == m

    standard_instance_with_ports.module = None
    with pytest.raises(ParentNotFoundError):
        standard_instance_with_ports.parent


def test_input_ports(standard_instance_with_ports: Instance) -> None:
    target_ports = (standard_instance_with_ports.ports['PortA'], standard_instance_with_ports.ports['PortB'])
    found_ports = standard_instance_with_ports.input_ports

    assert target_ports == found_ports


def test_output_ports(standard_instance_with_ports: Instance) -> None:
    target_ports = (standard_instance_with_ports.ports['PortC'],)
    found_ports = standard_instance_with_ports.output_ports

    assert target_ports == found_ports


def test_is_primitive_from_gatelib(standard_instance_with_ports: Instance) -> None:
    assert not standard_instance_with_ports.is_primitive_from_gatelib

    assert Instance(raw_path='', instance_type='§mux', module=None).is_primitive_from_gatelib

    assert not Instance(raw_path='', instance_type='§some_other_instance', module=None).is_primitive_from_gatelib


def test_verilog_template(standard_instance_with_ports: Instance) -> None:
    tmp = standard_instance_with_ports.verilog_template
    assert tmp == '{inst_type} {inst_name} ({ports});'


def test_verilog(standard_instance_with_ports: Instance) -> None:
    target_v = (
        'test_instance_type test_instance2 (\n\t.PortA(wire4b[1]),\n\t.PortB({wire4b[2], wire4b[3], wire4b[2], wire4b[1]}),\n\t.PortC(wire4b[4])\n);'
    )
    found_v = standard_instance_with_ports.verilog
    assert target_v == found_v


def test_port_is_known(standard_instance_with_ports: Instance) -> None:
    is_known = standard_instance_with_ports.port_is_known('PortA')
    assert is_known

    is_known = standard_instance_with_ports.port_is_known('invalid')
    assert not is_known


def test_add_connection(standard_instance_with_ports: Instance, locked_instance: Instance) -> None:
    standard_instance_with_ports.connect('PortD', WireSegmentPath(raw='a.b.c.xy'), index=0)
    assert len(standard_instance_with_ports.connections) == 4
    assert len(standard_instance_with_ports.connections['PortD']) == 1
    assert standard_instance_with_ports.connections['PortD'][0].name == 'xy'

    with pytest.raises(IdentifierConflictError):
        standard_instance_with_ports.connect('PortD', WireSegmentPath(raw='a.b.c.zw'), index=0)
    assert len(standard_instance_with_ports.connections) == 4
    assert len(standard_instance_with_ports.connections['PortD']) == 1
    assert standard_instance_with_ports.connections['PortD'][0].name == 'xy'

    standard_instance_with_ports.connect('PortA', WireSegmentPath(raw='a.b.c.uv'), index=1)
    assert len(standard_instance_with_ports.connections) == 4
    assert len(standard_instance_with_ports.connections['PortA']) == 2

    with pytest.raises(ObjectLockedError):
        locked_instance.connect('PortD', WireSegmentPath(raw='a.b.c.xy'), index=0)
    assert len(locked_instance.connections) == 3
    assert 'PortD' not in locked_instance.connections


def test_add_connection_4b(standard_instance_with_ports: Instance) -> None:
    s_inst = standard_instance_with_ports
    s_inst.connect('PortD', WireSegmentPath(raw='a.b.c.xy'), index=0, width=4)
    assert len(s_inst.connections) == 4
    assert len(s_inst.connections['PortD']) == 4
    assert s_inst.connections['PortD'][0].name == 'xy'
    assert s_inst.ports['PortD'].width == 4
    assert [0, 1, 2, 3] == list(s_inst.ports['PortD'].segments.keys())

    with pytest.raises(IdentifierConflictError):
        s_inst.connect('PortD', WireSegmentPath(raw='a.b.c.zw'), index=0, width=4)
    assert len(s_inst.connections) == 4
    assert len(s_inst.connections['PortD']) == 4
    assert s_inst.connections['PortD'][0].name == 'xy'

    with pytest.raises(IdentifierConflictError):
        s_inst.connect('PortA', WireSegmentPath(raw='a.b.c.uv'), index=0, width=4)
    assert len(s_inst.connections) == 4
    assert len(s_inst.connections['PortA']) == 1

    s_inst.connect('PortA', WireSegmentPath(raw='a.b.c.uv'), index=10, width=4)
    assert len(s_inst.connections) == 4
    assert len(s_inst.connections['PortA']) == 1 + 4  # 1 previously, 4 new
    assert s_inst.ports['PortA'].width == 5
    assert [0, 10, 11, 12, 13] == list(s_inst.ports['PortA'].segments.keys())


def test_remove_connection(standard_instance_with_ports: Instance, locked_instance: Instance) -> None:
    standard_instance_with_ports.disconnect('PortB', index=0)
    assert len(standard_instance_with_ports.connections) == 3
    assert len(standard_instance_with_ports.all_connections(include_unconnected=True)['PortB']) == 4
    assert len(standard_instance_with_ports.all_connections(include_unconnected=False)['PortB']) == 3
    assert 0 not in standard_instance_with_ports.all_connections(include_unconnected=False)['PortB']

    standard_instance_with_ports.disconnect('PortB', index=-1)
    assert len(standard_instance_with_ports.all_connections(include_unconnected=False)) == 2
    assert 'PortB' not in standard_instance_with_ports.all_connections(include_unconnected=False)

    with pytest.raises(ObjectNotFoundError):
        standard_instance_with_ports.disconnect('PortD', index=-1)
    assert len(standard_instance_with_ports.all_connections(include_unconnected=False)) == 2

    with pytest.raises(ObjectNotFoundError):
        standard_instance_with_ports.disconnect('PortA', index=2)
    assert len(standard_instance_with_ports.all_connections(include_unconnected=False)) == 2

    with pytest.raises(ObjectLockedError):
        locked_instance.disconnect('PortB', index=-1)
    assert len(locked_instance.connections) == 3
    assert 'PortB' in locked_instance.all_connections(include_unconnected=False)

    with pytest.raises(ObjectLockedError):
        locked_instance.disconnect('PortB', index=0)
    assert len(locked_instance.connections) == 3
    assert 0 in locked_instance.connections['PortB']


def test_get_connection(standard_instance_with_ports: Instance) -> None:
    connection = standard_instance_with_ports.get_connection('PortB')
    assert len(connection) == 4
    assert list(connection.keys()) == [0, 1, 2, 3]

    connection = standard_instance_with_ports.get_connection('PortB', index=0)
    assert connection.raw == 'test_module1.wire4b.2'

    connection = standard_instance_with_ports.get_connection('PortD')
    assert connection == {}

    connection = standard_instance_with_ports.get_connection('PortB', index=69)
    assert connection is None


def test_modify_connection(standard_instance_with_ports: Instance) -> None:
    assert standard_instance_with_ports.connections['PortA'][0].raw == 'test_module1.wire4b.1'
    assert standard_instance_with_ports.ports['PortA'][0].raw_ws_path == 'test_module1.wire4b.1'
    standard_instance_with_ports.modify_connection('PortA', WireSegmentPath(raw='test_module1.wire4b.1'))
    assert standard_instance_with_ports.connections['PortA'][0].raw == 'test_module1.wire4b.1'
    assert standard_instance_with_ports.ports['PortA'][0].raw_ws_path == 'test_module1.wire4b.1'

    standard_instance_with_ports.modify_connection('PortA', WireSegmentPath(raw='test_module1.wire2.seg1'))
    assert standard_instance_with_ports.connections['PortA'][0].raw == 'test_module1.wire2.seg1'
    assert standard_instance_with_ports.ports['PortA'][0].raw_ws_path == 'test_module1.wire2.seg1'

    assert standard_instance_with_ports.connections['PortB'][2].raw == 'test_module1.wire4b.2'
    standard_instance_with_ports.modify_connection('PortB', WireSegmentPath(raw='test_module1.wire2.seg1'), index=2)
    assert standard_instance_with_ports.connections['PortB'][0].raw == 'test_module1.wire4b.2'
    assert standard_instance_with_ports.ports['PortB'][0].raw_ws_path == 'test_module1.wire4b.2'
    assert standard_instance_with_ports.connections['PortB'][1].raw == 'test_module1.wire4b.3'
    assert standard_instance_with_ports.ports['PortB'][1].raw_ws_path == 'test_module1.wire4b.3'
    assert standard_instance_with_ports.connections['PortB'][2].raw == 'test_module1.wire2.seg1'
    assert standard_instance_with_ports.ports['PortB'][2].raw_ws_path == 'test_module1.wire2.seg1'
    assert standard_instance_with_ports.connections['PortB'][3].raw == 'test_module1.wire4b.1'
    assert standard_instance_with_ports.ports['PortB'][3].raw_ws_path == 'test_module1.wire4b.1'

    with pytest.raises(ObjectNotFoundError):
        standard_instance_with_ports.modify_connection('invalid', WireSegmentPath(raw=''))

    standard_instance_with_ports.change_mutability(is_now_locked=True)
    with pytest.raises(ObjectLockedError):
        standard_instance_with_ports.modify_connection('PortA', WireSegmentPath(raw='test_module1.wire3.seg1'))
    assert standard_instance_with_ports.connections['PortA'][0].raw == 'test_module1.wire2.seg1'

    standard_instance_with_ports.change_mutability(is_now_locked=False)
    standard_instance_with_ports.ports['PortA'].change_mutability(is_now_locked=True)
    with pytest.raises(ObjectLockedError):
        standard_instance_with_ports.modify_connection('PortA', WireSegmentPath(raw='test_module1.wire3.seg1'))
    assert standard_instance_with_ports.connections['PortA'][0].raw == 'test_module1.wire2.seg1'


def test_add_or_modify_connection(standard_instance_with_ports: Instance) -> None:
    standard_instance_with_ports.connect_modify('PortD', WireSegmentPath(raw='a.b.c.xy'), index=0)
    assert len(standard_instance_with_ports.connections) == 4
    assert len(standard_instance_with_ports.connections['PortD']) == 1
    assert standard_instance_with_ports.connections['PortD'][0].name == 'xy'

    standard_instance_with_ports.connect_modify('PortD', WireSegmentPath(raw='a.b.c.zw'), index=0)
    assert len(standard_instance_with_ports.connections) == 4
    assert len(standard_instance_with_ports.connections['PortD']) == 1
    assert standard_instance_with_ports.connections['PortD'][0].name == 'zw'

    standard_instance_with_ports.connect_modify('PortD', WireSegmentPath(raw='a.b.c.xy'), index=1)
    assert len(standard_instance_with_ports.connections) == 4
    assert len(standard_instance_with_ports.connections['PortD']) == 2
    assert standard_instance_with_ports.connections['PortD'][0].name == 'zw'
    assert standard_instance_with_ports.connections['PortD'][1].name == 'xy'

    standard_instance_with_ports.connect_modify('PortD', WireSegmentPath(raw='a.b.c.xy'), index=1)

    assert standard_instance_with_ports.connections['PortA'][0].raw == 'test_module1.wire4b.1'
    assert standard_instance_with_ports.ports['PortA'][0].raw_ws_path == 'test_module1.wire4b.1'
    standard_instance_with_ports.connect_modify('PortA', WireSegmentPath(raw='test_module1.wire4b.1'))


def test_tie_port(standard_instance_with_ports: Instance) -> None:
    assert standard_instance_with_ports.ports['PortA'][0].raw_ws_path == 'test_module1.wire4b.1'
    assert not standard_instance_with_ports.ports['PortA'][0].is_tied

    standard_instance_with_ports.ports['PortA'][0].set_ws_path('')
    standard_instance_with_ports.ports['PortC'][0].set_ws_path('')
    with pytest.raises(InvalidSignalError):
        standard_instance_with_ports.tie_port('PortA', 0, 'abc')
    assert standard_instance_with_ports.ports['PortA'][0].raw_ws_path == ''
    assert standard_instance_with_ports.ports['PortA'][0].is_tied

    standard_instance_with_ports.tie_port('PortA', 0, '0')
    assert standard_instance_with_ports.ports['PortA'][0].raw_ws_path == '0'
    assert standard_instance_with_ports.ports['PortA'][0].is_tied
    assert standard_instance_with_ports.ports['PortA'][0].signal == Signal.LOW

    standard_instance_with_ports.tie_port('PortA', 0, '1')
    assert standard_instance_with_ports.ports['PortA'][0].raw_ws_path == '1'
    assert standard_instance_with_ports.ports['PortA'][0].is_tied
    assert standard_instance_with_ports.ports['PortA'][0].signal == Signal.HIGH

    standard_instance_with_ports.tie_port('PortA', 0, 'Z')
    assert standard_instance_with_ports.ports['PortA'][0].raw_ws_path == 'Z'
    assert standard_instance_with_ports.ports['PortA'][0].is_tied
    assert standard_instance_with_ports.ports['PortA'][0].signal == Signal.FLOATING

    with pytest.raises(ObjectNotFoundError):
        standard_instance_with_ports.tie_port('PortA', 1, 'Z')

    # Do not allow forcing output ports to a constant value
    with pytest.raises(InvalidPortDirectionError):
        standard_instance_with_ports.tie_port('PortC', 0, '1')

    with pytest.raises(ObjectNotFoundError):
        standard_instance_with_ports.tie_port('UnknownPort', 0, 'Z')


def test_has_tied_ports(standard_instance_with_ports: Instance) -> None:
    assert not standard_instance_with_ports.has_tied_ports()
    standard_instance_with_ports.modify_connection('PortC', WIRE_SEGMENT_X.path)
    assert standard_instance_with_ports.has_tied_ports()
    standard_instance_with_ports.modify_connection('PortC', WIRE_SEGMENT_1.path)
    assert standard_instance_with_ports.has_tied_ports()

    standard_instance_with_ports.modify_connection('PortA', WIRE_SEGMENT_X.path)
    assert standard_instance_with_ports.has_tied_ports()
    standard_instance_with_ports.modify_connection('PortA', WIRE_SEGMENT_1.path)
    assert standard_instance_with_ports.has_tied_ports()

    standard_instance_with_ports.modify_connection('PortC', WireSegmentPath(raw='test_module1.wire4b.1'))
    assert standard_instance_with_ports.has_tied_ports()
    standard_instance_with_ports.modify_connection('PortA', WireSegmentPath(raw='test_module1.wire4b.1'))
    assert not standard_instance_with_ports.has_tied_ports()


def test_has_tied_inputs(standard_instance_with_ports: Instance) -> None:
    assert not standard_instance_with_ports.has_tied_inputs()
    standard_instance_with_ports.modify_connection('PortC', WIRE_SEGMENT_X.path)
    assert not standard_instance_with_ports.has_tied_inputs()
    standard_instance_with_ports.modify_connection('PortC', WIRE_SEGMENT_1.path)
    assert not standard_instance_with_ports.has_tied_inputs()

    standard_instance_with_ports.modify_connection('PortA', WIRE_SEGMENT_X.path)
    assert standard_instance_with_ports.has_tied_inputs()
    standard_instance_with_ports.modify_connection('PortA', WIRE_SEGMENT_1.path)
    assert standard_instance_with_ports.has_tied_inputs()


def test_has_tied_outputs(standard_instance_with_ports: Instance) -> None:
    assert not standard_instance_with_ports.has_tied_outputs()
    standard_instance_with_ports.modify_connection('PortA', WIRE_SEGMENT_X.path)
    assert not standard_instance_with_ports.has_tied_outputs()
    standard_instance_with_ports.modify_connection('PortA', WIRE_SEGMENT_1.path)
    assert not standard_instance_with_ports.has_tied_outputs()

    standard_instance_with_ports.modify_connection('PortC', WIRE_SEGMENT_X.path)
    assert standard_instance_with_ports.has_tied_outputs()
    standard_instance_with_ports.modify_connection('PortC', WIRE_SEGMENT_1.path)
    assert standard_instance_with_ports.has_tied_outputs()


def test_set_name(standard_instance_with_ports: Instance) -> None:
    standard_instance_with_ports.set_name('SOME_INST')
    assert standard_instance_with_ports.name == 'SOME_INST'
    for p in standard_instance_with_ports.ports.values():
        assert p.path[1] == 'SOME_INST'
        for _, ps in p:
            assert ps.path[1] == 'SOME_INST'


def test_change_mutability(standard_instance_with_ports: Instance) -> None:
    assert not standard_instance_with_ports.locked
    standard_instance_with_ports.change_mutability(is_now_locked=True)
    assert standard_instance_with_ports.locked
    assert not standard_instance_with_ports.ports['PortA'].locked
    assert not standard_instance_with_ports.ports['PortB'].locked
    assert not standard_instance_with_ports.ports['PortC'].locked

    standard_instance_with_ports.change_mutability(is_now_locked=True, recursive=True)
    assert standard_instance_with_ports.locked
    assert standard_instance_with_ports.ports['PortA'].locked
    assert standard_instance_with_ports.ports['PortB'].locked
    assert standard_instance_with_ports.ports['PortC'].locked


def test_normalize_metadata(standard_instance_with_ports: Instance) -> None:
    found = standard_instance_with_ports.normalize_metadata()
    assert found == {}
    found = standard_instance_with_ports.normalize_metadata(include_empty=True)
    target: METADATA_DICT = {
        'test_module1.test_instance2': {},
        'test_module1.test_instance2.PortA': {},
        'test_module1.test_instance2.PortA.0': {},
        'test_module1.test_instance2.PortB': {},
        'test_module1.test_instance2.PortB.0': {},
        'test_module1.test_instance2.PortB.1': {},
        'test_module1.test_instance2.PortB.2': {},
        'test_module1.test_instance2.PortB.3': {},
        'test_module1.test_instance2.PortC': {},
        'test_module1.test_instance2.PortC.0': {},
    }
    assert found == target
    standard_instance_with_ports.metadata.set('foo', 'bar')
    standard_instance_with_ports.metadata.set('foo', 'baz', 'cat')
    standard_instance_with_ports.ports['PortA'][0].metadata.set('foo', 'bar')
    standard_instance_with_ports.ports['PortC'].metadata.set('foo', 'baz', 'cat')
    found = standard_instance_with_ports.normalize_metadata()
    target2: METADATA_DICT = {
        'test_module1.test_instance2': {'general': {'foo': 'bar'}, 'cat': {'foo': 'baz'}},
        'test_module1.test_instance2.PortA.0': {'general': {'foo': 'bar'}},
        'test_module1.test_instance2.PortC': {'cat': {'foo': 'baz'}},
    }
    assert found == target2
    found = standard_instance_with_ports.normalize_metadata(sort_by='category')
    target3: METADATA_DICT = {
        'general': {
            'test_module1.test_instance2': {'foo': 'bar'},
            'test_module1.test_instance2.PortA.0': {'foo': 'bar'},
        },
        'cat': {
            'test_module1.test_instance2': {'foo': 'baz'},
            'test_module1.test_instance2.PortC': {'foo': 'baz'},
        },
    }
    assert found == target3

    # Checks if {"foo": "bar"} is part of val
    found = standard_instance_with_ports.normalize_metadata(sort_by='category', filter=lambda cat, md: 'foo' in md and md['foo'] == 'bar')
    target4: METADATA_DICT = {'general': {'test_module1.test_instance2': {'foo': 'bar'}, 'test_module1.test_instance2.PortA.0': {'foo': 'bar'}}}
    assert found == target4

    # Illegal operation should be resolved to False
    found = standard_instance_with_ports.normalize_metadata(sort_by='category', filter=lambda cat, md: md.is_integer())
    assert found == {}


def test_instance_hash(standard_instance_with_ports: Instance) -> None:
    assert hash(standard_instance_with_ports) == hash(standard_instance_with_ports)

    siwp2 = copy.deepcopy(standard_instance_with_ports)
    assert hash(standard_instance_with_ports) == hash(siwp2)

    siwp2.ports['PortB'][2].raw_path = siwp2.ports['PortB'][2].raw_path[:-1] + '42'
    assert hash(standard_instance_with_ports) != hash(siwp2)


def test_instance_str(empty_standard_instance: Instance) -> None:
    # Test the string representation of a instance
    assert str(empty_standard_instance) == 'Instance "test_instance1" with path test_module1.test_instance1 (type test_instance_type)'


def test_instance_repr(empty_standard_instance: Instance) -> None:
    # Test the representation of a instance
    assert repr(empty_standard_instance) == 'Instance(test_instance_type: test_module1.test_instance1)'


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
