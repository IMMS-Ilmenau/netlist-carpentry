import json
import os

import pytest

from netlist_carpentry.api.read.read_utils import read
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.exceptions import (
    IdentifierConflictError,
    ObjectNotFoundError,
    PathResolutionError,
    SignalAssignmentError,
)
from netlist_carpentry.core.netlist_elements.element_path import (
    InstancePath,
    PortPath,
    PortSegmentPath,
    WirePath,
    WireSegmentPath,
)
from netlist_carpentry.core.netlist_elements.mixins.metadata import METADATA_DICT
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.signal import Signal


@pytest.fixture
def empty_circuit() -> Circuit:
    return Circuit(name='test_circuit')


@pytest.fixture
def connected_circuit() -> Circuit:
    from utils import connected_circuit

    return connected_circuit()


def test_circuit_creation(empty_circuit: Circuit) -> None:
    assert empty_circuit.name == 'test_circuit'
    assert empty_circuit.modules == {}
    assert empty_circuit.module_count == 0
    assert len(empty_circuit) == 0
    assert empty_circuit.module_names == {0} - {0}  # Funny eyes <=> empty set
    assert empty_circuit.creator == ''
    assert len(empty_circuit) == 0
    with pytest.raises(IndexError):
        empty_circuit.first


def test_add_module(empty_circuit: Circuit) -> None:
    assert empty_circuit.module_names == {0} - {0}  # Funny eyes <=> empty set

    m = Module(raw_path='testModule')
    added = empty_circuit.add_module(m)

    assert added == m
    assert empty_circuit.module_count == 1
    assert len(empty_circuit) == 1
    assert empty_circuit['testModule'] == m
    assert empty_circuit.modules['testModule'] == m
    assert empty_circuit.module_names == {'testModule'}
    assert empty_circuit.first == m

    m2 = Module(raw_path='testModule', parameters={'foo': 'bar'})
    with pytest.raises(IdentifierConflictError):
        empty_circuit.add_module(m2)
    assert empty_circuit.module_count == 1
    assert len(empty_circuit) == 1
    assert empty_circuit.module_names == {'testModule'}
    assert empty_circuit.first == m


def test_add_from_circuit(empty_circuit: Circuit, connected_circuit: Circuit) -> None:
    added = empty_circuit.add_from_circuit(connected_circuit)
    assert added == connected_circuit.modules
    assert connected_circuit.module_count == 2
    assert empty_circuit.module_count == 2
    for m in connected_circuit:
        assert id(m) == id(empty_circuit[m.name])
        m.create_wire('ABC')
        assert 'ABC' in empty_circuit[m.name].wires

    with pytest.raises(IdentifierConflictError):
        empty_circuit.add_from_circuit(connected_circuit)


def test_create_module(empty_circuit: Circuit) -> None:
    assert empty_circuit.module_names == {0} - {0}  # Funny eyes <=> empty set

    created = empty_circuit.create_module('testModule')

    assert created.name == 'testModule'
    assert empty_circuit.module_count == 1
    assert len(empty_circuit) == 1
    assert empty_circuit.module_names == {'testModule'}

    with pytest.raises(IdentifierConflictError):
        empty_circuit.create_module('testModule')
    assert empty_circuit.module_count == 1
    assert len(empty_circuit) == 1
    assert empty_circuit.module_names == {'testModule'}


def test_remove_module(empty_circuit: Circuit) -> None:
    m = Module(raw_path='testModule')
    empty_circuit.add_module(m)
    empty_circuit.set_top(m)
    assert empty_circuit.module_count == 1
    assert len(empty_circuit) == 1
    assert empty_circuit['testModule'] == m
    assert empty_circuit.modules['testModule'] == m
    assert empty_circuit.module_names == {'testModule'}
    assert empty_circuit.top_name == 'testModule'

    empty_circuit.remove_module(m.name)
    assert empty_circuit.module_count == 0
    assert len(empty_circuit) == 0
    assert empty_circuit.module_names == {0} - {0}  # Funny eyes <=> empty set
    assert empty_circuit.top_name == ''

    with pytest.raises(ObjectNotFoundError):
        empty_circuit.remove_module(m.name)
    assert empty_circuit.module_count == 0
    assert len(empty_circuit) == 0
    assert empty_circuit.module_names == {0} - {0}  # Funny eyes <=> empty set


def test_get_module(empty_circuit: Circuit) -> None:
    m = Module(raw_path='testModule')
    empty_circuit.add_module(m)

    m2 = empty_circuit.get_module(m.name)

    assert m2 == m
    assert m2 == empty_circuit['testModule']
    assert m2 == empty_circuit.modules['testModule']

    m3 = empty_circuit.get_module('invalid')

    assert m3 is None


def test_get_module_idx(empty_circuit: Circuit) -> None:
    get_m = empty_circuit.get_module_at_idx(0)
    assert get_m is None
    with pytest.raises(IndexError):
        empty_circuit.first

    m = Module(raw_path='testModule')
    empty_circuit.add_module(m)
    get_m = empty_circuit.get_module_at_idx(0)
    assert get_m is m
    assert empty_circuit.first == m
    get_m = empty_circuit.get_module_at_idx(1)
    assert get_m is None

    m2 = Module(raw_path='testModule2')
    empty_circuit.add_module(m2)
    get_m = empty_circuit.get_module_at_idx(0)
    assert get_m is m
    get_m = empty_circuit.get_module_at_idx(1)
    assert get_m is m2
    get_m = empty_circuit.get_module_at_idx(2)
    assert get_m is None


def test_set_top_module(connected_circuit: Circuit) -> None:
    assert connected_circuit.top_name == 'wrapper'
    assert connected_circuit.top == connected_circuit['wrapper']
    assert connected_circuit.has_top

    with pytest.raises(ObjectNotFoundError):
        connected_circuit.set_top('')
    assert connected_circuit.top_name == 'wrapper'
    assert connected_circuit.top == connected_circuit['wrapper']
    assert connected_circuit.has_top

    connected_circuit.set_top('test_module1')
    assert connected_circuit.top_name == 'test_module1'
    assert connected_circuit.top == connected_circuit['test_module1']
    assert connected_circuit.has_top

    connected_circuit._top_name = ''
    assert connected_circuit.top_name == ''
    with pytest.raises(ObjectNotFoundError):
        assert connected_circuit.top
    assert not connected_circuit.has_top


def test_get_from_path(connected_circuit: Circuit) -> None:
    path_inst = PortPath(raw='')
    with pytest.raises(PathResolutionError):
        inst = connected_circuit.get_from_path(path_inst)

    path_inst = None
    with pytest.raises(PathResolutionError):
        inst = connected_circuit.get_from_path(path_inst)

    path_inst = PortPath(raw='wrapper.in1')
    inst = connected_circuit.get_from_path(path_inst)
    assert inst == connected_circuit['wrapper'].ports['in1']

    path_inst = InstancePath(raw='wrapper.I_cm')
    inst = connected_circuit.get_from_path(path_inst)
    assert inst == connected_circuit['wrapper'].instances['I_cm']

    path_inst = InstancePath(raw='wrapper.I_cm.non_existing_inst.non_existing')
    with pytest.raises(PathResolutionError):
        inst = connected_circuit.get_from_path(path_inst)

    path_inst = PortPath(raw='wrapper.I_cm.in1')
    inst = connected_circuit.get_from_path(path_inst)
    assert inst == connected_circuit['wrapper'].instances['I_cm'].ports['in1']

    path_inst = InstancePath(raw='wrapper.I_cm.and_inst')
    inst = connected_circuit.get_from_path(path_inst)
    assert inst == connected_circuit['test_module1'].instances['and_inst']

    path_inst = PortPath(raw='wrapper.I_cm.and_inst.A')
    inst = connected_circuit.get_from_path(path_inst)
    assert inst == connected_circuit['test_module1'].instances['and_inst'].ports['A']

    path_inst = PortSegmentPath(raw='wrapper.I_cm.and_inst.A.0')
    inst = connected_circuit.get_from_path(path_inst)
    assert inst == connected_circuit['test_module1'].instances['and_inst'].ports['A'][0]


def test_get_from_path_overload(connected_circuit: Circuit) -> None:
    with pytest.raises(PathResolutionError):
        connected_circuit.get_from_path('')

    raw_path = 'wrapper.in1'
    inst = connected_circuit.get_from_path(raw_path)
    assert inst == connected_circuit['wrapper'].ports['in1']

    raw_path = 'wrapper.I_cm'
    inst = connected_circuit.get_from_path(raw_path)
    assert inst == connected_circuit['wrapper'].instances['I_cm']

    raw_path = 'wrapper.I_cm.in1'
    inst = connected_circuit.get_from_path(raw_path)
    assert inst == connected_circuit['wrapper'].instances['I_cm'].ports['in1']

    raw_path = 'wrapper.I_cm.and_inst'
    inst = connected_circuit.get_from_path(raw_path)
    assert inst == connected_circuit['test_module1'].instances['and_inst']

    raw_path = 'wrapper.I_cm.and_inst.A'
    inst = connected_circuit.get_from_path(raw_path)
    assert inst == connected_circuit['test_module1'].instances['and_inst'].ports['A']

    raw_path = 'wrapper.I_cm.and_inst.A.0'
    inst = connected_circuit.get_from_path(raw_path)
    assert inst == connected_circuit['test_module1'].instances['and_inst'].ports['A'][0]


def test_get_path_from_str(connected_circuit: Circuit) -> None:
    bad_path = ''
    with pytest.raises(PathResolutionError):
        assert connected_circuit.get_path_from_str(bad_path)

    bad_path = 'abc'
    with pytest.raises(PathResolutionError):
        assert connected_circuit.get_path_from_str(bad_path)

    bad_path = 'wrapper.abc'
    with pytest.raises(PathResolutionError):
        assert connected_circuit.get_path_from_str(bad_path)

    bad_path = 'wrapper.in1.abc'
    with pytest.raises(PathResolutionError):
        assert connected_circuit.get_path_from_str(bad_path)

    bad_path = 'wrapper.I_cm.abc'
    with pytest.raises(PathResolutionError):
        assert connected_circuit.get_path_from_str(bad_path)

    bad_path = 'wrapper.I_cm.and_inst.abc'
    with pytest.raises(PathResolutionError):
        assert connected_circuit.get_path_from_str(bad_path)

    raw_path = 'wrapper.in1'
    inst = connected_circuit.get_path_from_str(raw_path)
    assert inst == connected_circuit['wrapper'].ports['in1'].path

    raw_path = 'wrapper.in1'
    with pytest.raises(PathResolutionError):
        connected_circuit.get_path_from_str(raw_path, '!')

    raw_path = 'wrapper/in1'
    inst = connected_circuit.get_path_from_str(raw_path, '/')
    assert inst == connected_circuit['wrapper'].ports['in1'].path

    raw_path = 'wrapper.I_cm'
    inst = connected_circuit.get_path_from_str(raw_path)
    assert inst == connected_circuit['wrapper'].instances['I_cm'].path

    raw_path = 'wrapper.I_cm.in1'
    inst = connected_circuit.get_path_from_str(raw_path)
    assert inst == connected_circuit['wrapper'].instances['I_cm'].ports['in1'].path

    raw_path = 'wrapper.I_cm.and_inst'
    inst = connected_circuit.get_path_from_str(raw_path)
    assert inst == InstancePath(raw='wrapper.I_cm.and_inst')

    raw_path = 'wrapper.I_cm.and_inst.A'
    inst = connected_circuit.get_path_from_str(raw_path)
    assert inst == PortPath(raw='wrapper.I_cm.and_inst.A')

    raw_path = 'wrapper.I_cm.and_inst.A.0'
    inst = connected_circuit.get_path_from_str(raw_path)
    assert inst == PortSegmentPath(raw='wrapper.I_cm.and_inst.A.0')

    raw_path = 'wrapper.I_cm.wire_and'
    inst = connected_circuit.get_path_from_str(raw_path)
    assert inst == WirePath(raw='wrapper.I_cm.wire_and')

    raw_path = 'wrapper.I_cm.wire_and.0'
    inst = connected_circuit.get_path_from_str(raw_path)
    assert inst == WireSegmentPath(raw='wrapper.I_cm.wire_and.0')


def test_connected_circuit(connected_circuit: Circuit) -> None:
    assert connected_circuit.creator == 'SomeCreator'
    assert connected_circuit.module_count == 2
    assert 'test_module1' in connected_circuit.modules
    assert 'wrapper' in connected_circuit.modules
    assert connected_circuit.module_names == {'test_module1', 'wrapper'}
    for module in connected_circuit:
        assert module.name == 'test_module1' or module.name == 'wrapper'

    wrapper = connected_circuit.get_module('wrapper')
    test_module1 = connected_circuit.get_module('test_module1')
    test_module_inst = wrapper.get_instance('I_cm')
    assert wrapper.ports.keys() == test_module1.ports.keys()
    assert wrapper.submodules == {test_module_inst}
    for pname in wrapper.ports:
        assert test_module_inst.ports[pname][0].ws_path == wrapper.ports[pname][0].ws_path


def test_set_signal(connected_circuit: Circuit) -> None:
    raw_path = 'faafn.foofn'
    with pytest.raises(PathResolutionError):
        connected_circuit.set_signal(raw_path, '0')

    raw_path = 'wrapper.in1'
    connected_circuit.set_signal(raw_path, '0')
    assert connected_circuit['wrapper'].ports['in1'].signal == Signal.LOW

    raw_path = 'wrapper.I_cm'
    with pytest.raises(SignalAssignmentError):
        connected_circuit.set_signal(raw_path, Signal.HIGH)

    raw_path = 'wrapper.I_cm.in1'
    connected_circuit.set_signal(raw_path, '1')
    assert connected_circuit['wrapper'].instances['I_cm'].ports['in1'].signal == Signal.HIGH

    raw_path = 'wrapper.I_cm.and_inst'
    with pytest.raises(SignalAssignmentError):
        connected_circuit.set_signal(raw_path, Signal.LOW)

    raw_path = 'wrapper.I_cm.and_inst.A'
    connected_circuit.set_signal(raw_path, Signal.HIGH)
    assert connected_circuit['test_module1'].instances['and_inst'].ports['A'].signal == Signal.HIGH

    raw_path = 'wrapper.I_cm.and_inst.A.0'
    connected_circuit.set_signal(raw_path, Signal.LOW)
    assert connected_circuit['test_module1'].instances['and_inst'].ports['A'][0].signal == Signal.LOW


def test_write(connected_circuit: Circuit) -> None:
    vpath = 'tests/files/gen/connected_circuit.v'
    if os.path.exists(vpath):
        os.remove(vpath)
    connected_circuit.write(vpath)
    assert os.path.exists(vpath)


@pytest.mark.skip
def test_prove_equivalence(connected_circuit: Circuit) -> None:
    vpath = 'tests/files/gen/connected_circuit.v'
    connected_circuit.write(vpath, True)
    return_code = connected_circuit.prove_equivalence([vpath], 'tests/files/gen/eqy_out')

    assert return_code == 0


@pytest.mark.skip
def test_prove_equivalence_other_circuit(connected_circuit: Circuit) -> None:
    vpath = 'tests/files/gen/connected_circuit.v'
    other_circuit = read(vpath)
    connected_circuit.write(vpath, True)
    return_code = connected_circuit.prove_equivalence(other_circuit, 'tests/files/gen/eqy_out')

    assert return_code == 0


def test_optimize(connected_circuit: Circuit) -> None:
    connected_module = connected_circuit.modules['test_module1']
    assert len(connected_module.wires) == 12
    assert len(connected_module.instances) == 5
    any_removed = connected_circuit.optimize()  # Removes unused wire "en"
    assert any_removed
    assert len(connected_module.wires) == 11
    assert len(connected_module.instances) == 5

    any_removed = connected_circuit.optimize()  # Nothing removed
    assert not any_removed
    assert len(connected_module.wires) == 11
    assert len(connected_module.instances) == 5

    connected_module.disconnect(connected_module.ports['out'][0])
    any_removed = connected_circuit.optimize()  # Removes now unused wire "out" and instance
    assert any_removed
    assert len(connected_module.wires) == 10
    assert len(connected_module.instances) == 4

    connected_module.disconnect(connected_module.ports['out_ff'][0])
    any_removed = connected_circuit.optimize()  # Removes now unused wire "out_ff" and all connected instances
    assert any_removed
    assert len(connected_module.wires) == 0
    assert len(connected_module.instances) == 0


def test_evaluate(connected_circuit: Circuit) -> None:
    wrapper = connected_circuit.get_module('wrapper')
    in1 = wrapper.get_port('in1')
    in2 = wrapper.get_port('in2')
    in3 = wrapper.get_port('in3')
    in4 = wrapper.get_port('in4')
    clk = wrapper.get_port('clk')
    rst = wrapper.get_port('rst')
    out = wrapper.get_port('out')
    out_ff = wrapper.get_port('out_ff')

    in1.set_signal(Signal.LOW)
    in2.set_signal(Signal.LOW)
    in3.set_signal(Signal.LOW)
    in4.set_signal(Signal.LOW)
    clk.set_signal(Signal.LOW)
    rst.set_signal(Signal.HIGH)
    connected_circuit.evaluate()

    assert out.signal == Signal.HIGH
    assert out_ff.signal == Signal.UNDEFINED

    in1.set_signal(Signal.LOW)
    in2.set_signal(Signal.LOW)
    in3.set_signal(Signal.LOW)
    in4.set_signal(Signal.LOW)
    clk.set_signal(Signal.LOW)
    rst.set_signal(Signal.LOW)
    connected_circuit.evaluate()

    in1.set_signal(Signal.LOW)
    in2.set_signal(Signal.LOW)
    in3.set_signal(Signal.HIGH)
    in4.set_signal(Signal.LOW)
    clk.set_signal(Signal.LOW)
    rst.set_signal(Signal.HIGH)
    connected_circuit.evaluate()

    in1.set_signal(Signal.LOW)
    in2.set_signal(Signal.LOW)
    in3.set_signal(Signal.HIGH)
    in4.set_signal(Signal.LOW)
    clk.set_signal(Signal.HIGH)
    rst.set_signal(Signal.HIGH)
    connected_circuit.evaluate()

    assert out.signal == Signal.LOW
    assert out_ff.signal == Signal.HIGH


def test_export_metadata(connected_circuit: Circuit) -> None:
    path = 'tests/files/gen/circuit_md.json'
    if os.path.exists(path):
        os.remove(path)
    connected_circuit.export_metadata(path, include_empty=True)
    assert os.path.exists(path)
    with open(path) as f:
        found_data = json.loads(f.read())
    assert len(found_data) == 96  # Too much to check directly
    os.remove(path)
    connected_circuit['wrapper'].metadata.set('foo', 'bar')
    connected_circuit['test_module1'].metadata.set('foo', 'bar')
    connected_circuit['test_module1'].metadata.set('foo', 'baz', 'cat')
    connected_circuit['test_module1'].ports['in1'][0].metadata.set('foo', 'bar')
    connected_circuit['test_module1'].wires['in4'].metadata.set('foo', 'baz', 'cat')
    connected_circuit.export_metadata(path)
    target_data2: METADATA_DICT = {
        'test_module1': {'general': {'foo': 'bar'}, 'cat': {'foo': 'baz'}},
        'test_module1.in1.0': {'general': {'foo': 'bar'}},
        'test_module1.in4': {'cat': {'foo': 'baz'}},
        'wrapper': {'general': {'foo': 'bar'}},
    }
    with open(path) as f:
        found_data = json.loads(f.read())
    assert found_data == target_data2

    connected_circuit.export_metadata(path, sort_by='category')
    target_data3: METADATA_DICT = {
        'general': {
            'test_module1': {'foo': 'bar'},
            'test_module1.in1.0': {'foo': 'bar'},
            'wrapper': {'foo': 'bar'},
        },
        'cat': {
            'test_module1': {'foo': 'baz'},
            'test_module1.in4': {'foo': 'baz'},
        },
    }
    with open(path) as f:
        found_data = json.loads(f.read())
    assert found_data == target_data3
    os.remove(path)

    connected_circuit.export_metadata(path, sort_by='category', filter=lambda cat, md: 'foo' in md and md['foo'] == 'bar')
    target_data4: METADATA_DICT = {'general': {'test_module1': {'foo': 'bar'}, 'test_module1.in1.0': {'foo': 'bar'}, 'wrapper': {'foo': 'bar'}}}
    with open(path) as f:
        found_data = json.loads(f.read())
    assert found_data == target_data4
    os.remove(path)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
