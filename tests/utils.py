import cProfile
import datetime
import inspect
import os
import pstats
from typing import Callable, Union

from typing_extensions import TypeAlias

from netlist_carpentry import CFG
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.netlist_elements.element_path import WirePath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire import Wire
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.core.signal import Signal
from netlist_carpentry.utils.gate_lib import NotGate, XorGate

StrOrBytesPath: TypeAlias = Union[str, bytes, os.PathLike[str], os.PathLike[bytes]]


def save_results(text_to_save: str, format_extension: str = '', additional_name: str = '') -> None:
    additional_name = '.' + additional_name if additional_name else ''
    prev_frame = inspect.stack()[1]
    fpath = prev_frame.filename
    fname = fpath[fpath.rindex('/') + 1 : fpath.rindex('.')]
    fnc_name = prev_frame.function
    comment_char = '//' if format_extension == 'v' else '#'
    name = f'{fname}.{fnc_name}{additional_name}.{format_extension}'.replace(CFG.id_internal, CFG.id_external)
    os.makedirs('tests/files/gen', exist_ok=True)
    with open(f'tests/files/gen/{name}', 'w') as f:
        f.write(f'{comment_char} Test results from {datetime.datetime.now().strftime("%d. %B %Y, %H:%M:%S")}\n\n')
        f.write(text_to_save)


def profile(fnc: Callable[..., Union[None, object]], path: str, **kwargs: object) -> object:
    with open(path, 'w') as f:
        profiler = cProfile.Profile()
        profiler.enable()
        val = fnc(**kwargs)
        profiler.disable()

        stats = pstats.Stats(profiler, stream=f)
        stats.sort_stats(pstats.SortKey.CUMULATIVE)  # Sort by execution time
        stats.print_stats()  # Write to file
    return val


def standard_instance_with_ports() -> Instance:
    m = empty_module()
    m.add_wire(wire_4b())
    inst = Instance(raw_path='test_module1.test_instance2', instance_type='test_instance_type', is_primitive=True, module=m)
    inst.connect('PortA', WireSegmentPath(raw='test_module1.wire4b.1'), direction=PortDirection.IN, index=0)
    inst.connect('PortB', WireSegmentPath(raw='test_module1.wire4b.2'), direction=PortDirection.IN, index=0)
    inst.connect('PortB', WireSegmentPath(raw='test_module1.wire4b.3'), index=1)
    inst.connect('PortB', WireSegmentPath(raw='test_module1.wire4b.2'), index=2)
    inst.connect('PortB', WireSegmentPath(raw='test_module1.wire4b.1'), direction=PortDirection.OUT, index=3)
    inst.connect('PortC', WireSegmentPath(raw='test_module1.wire4b.4'), direction=PortDirection.OUT, index=0)
    m.add_instance(inst)
    return inst


def locked_instance() -> Instance:
    inst = standard_instance_with_ports()
    return inst.change_mutability(True)


def standard_port_in() -> Port[Instance]:
    inst = Instance(raw_path='test_module1.some_test_inst', instance_type='some_type')
    p = Port(raw_path='test_module1.test_port1', direction=PortDirection.IN, module_or_instance=inst)
    p.create_port_segment(0)
    return p


def standard_port_out() -> Port[Module]:
    module = Module(raw_path='some_other_module')
    p = Port(raw_path='test_module1.test_port2', direction=PortDirection.OUT, msb_first=False, module_or_instance=module)
    p.create_port_segment(0).set_ws_path('test_module1.wire1.0')
    p.create_port_segment(1).set_ws_path('test_module1.wire1.0')
    return p


def locked_port() -> Port[Module]:
    p = Port(raw_path='', direction=PortDirection.IN_OUT, module_or_instance=Module(raw_path=''))
    p.create_port_segment(0)
    return p.change_mutability(True)


def standard_wire() -> Wire:
    p1 = Port(raw_path='test_module1.c.p1', direction=PortDirection.OUT, module_or_instance=Instance(raw_path='test_module1.c', instance_type='foo'))
    p2 = Port(raw_path='test_module1.d.p2', direction=PortDirection.IN, module_or_instance=Instance(raw_path='test_module1.d', instance_type='foo'))
    p3 = Port(raw_path='test_module1.p3', direction=PortDirection.OUT, module_or_instance=Module(raw_path='test_module1'))
    ps1 = p1.create_port_segment(0).set_ws_path('test_module1.wire1')
    ps2 = p2.create_port_segment(0).set_ws_path('test_module1.wire1')
    ps3 = p3.create_port_segment(0).set_ws_path('test_module1.wire1')

    w = Wire(raw_path='test_module1.wire1', module=None)
    w.create_wire_segment(1).add_port_segments([ps1, ps2, ps3])
    return w


def wire_1b() -> Wire:
    p1 = Port(raw_path='test_module1.a.p1', direction=PortDirection.OUT, module_or_instance=Instance(raw_path='test_module1.a', instance_type='foo'))
    p2 = Port(raw_path='test_module1.b.p2', direction=PortDirection.IN, module_or_instance=Instance(raw_path='test_module1.b', instance_type='foo'))
    p1.create_port_segment(0)
    p2.create_port_segment(0)
    w = Wire(raw_path='test_module1.wire1b', module=None)
    w.create_wire_segment(1).add_port_segments([p1[0], p2[0]])
    return w


def wire_4b() -> Wire:
    p1 = Port(raw_path='test_module1.a.p1', direction=PortDirection.OUT, module_or_instance=Instance(raw_path='test_module1.a', instance_type='foo'))
    p2 = Port(raw_path='test_module1.b.p2', direction=PortDirection.IN, module_or_instance=Instance(raw_path='test_module1.b', instance_type='foo'))
    p3 = Port(raw_path='test_module1.p3', direction=PortDirection.OUT, module_or_instance=Module(raw_path='test_module1'))
    p1.create_port_segment(0)
    p2.create_port_segment(0)
    p3.create_port_segment(0)
    ps = [p1[0], p2[0], p3[0]]
    w = Wire(raw_path='test_module1.wire4b', msb_first=False, module=None)
    w.create_wire_segment(1).add_port_segments(ps)
    w.create_wire_segment(2).add_port_segments(ps)
    w.create_wire_segment(3).add_port_segments(ps)
    w.create_wire_segment(4).add_port_segments(ps)
    return w


def locked_wire() -> Wire:
    w = Wire(raw_path='locked_wire', module=None)
    w._add_wire_segment(locked_wire_segment())
    return w.change_mutability(True)


def locked_wire_segment() -> WireSegment:
    p = Port(raw_path='p1', direction=PortDirection.IN_OUT, module_or_instance=None)
    p.create_port_segment(0)
    ports = [p[0]]
    w = WireSegment(raw_path='locked_seg.0', wire=None)
    w.add_port_segments(ports)
    return w.change_mutability(True)


def empty_module() -> Module:
    return Module(raw_path='test_module1')


def locked_module() -> Module:
    m = Module(raw_path='locked_module')
    m.add_instance(Instance(raw_path='test_inst', instance_type='test_type'))
    m.create_port('test_port', direction=PortDirection.IN_OUT)
    m.create_wire('test_wire')
    return m.change_mutability(True)


def connected_module() -> Module:
    from netlist_carpentry.utils.gate_lib import DFF, AndGate, NotGate, OrGate, XorGate

    m = empty_module()

    m.create_wire('in1')
    m.create_wire('in2')
    m.create_wire('in3')
    m.create_wire('in4')
    m.create_wire('clk')
    m.create_wire('rst')
    m.create_wire('en')
    m.create_wire('wire_or')
    m.create_wire('wire_and')
    m.create_wire('wire_xor')
    m.create_wire('out')
    m.create_wire('out_ff')

    m.connect(WirePath(raw=f'{m.name}.in1'), m.create_port('in1', PortDirection.IN))
    m.connect(WirePath(raw=f'{m.name}.in2'), m.create_port('in2', PortDirection.IN))
    m.connect(WirePath(raw=f'{m.name}.in3'), m.create_port('in3', PortDirection.IN))
    m.connect(WirePath(raw=f'{m.name}.in4'), m.create_port('in4', PortDirection.IN))
    m.connect(WirePath(raw=f'{m.name}.clk'), m.create_port('clk', PortDirection.IN))
    m.connect(WirePath(raw=f'{m.name}.rst'), m.create_port('rst', PortDirection.IN))
    m.connect(WirePath(raw=f'{m.name}.out'), m.create_port('out', PortDirection.OUT))
    m.connect(WirePath(raw=f'{m.name}.out_ff'), m.create_port('out_ff', PortDirection.OUT))

    m.add_instance(AndGate(raw_path=f'{m.name}.and_inst'))
    m.add_instance(OrGate(raw_path=f'{m.name}.or_inst'))
    m.add_instance(XorGate(raw_path=f'{m.name}.xor_inst'))
    m.add_instance(NotGate(raw_path=f'{m.name}.not_inst'))
    m.add_instance(DFF(raw_path=f'{m.name}.dff_inst', rst_polarity=Signal.LOW))

    m.connect(m.wires['in1'][0], m.instances['and_inst'].ports['A'][0])
    m.connect(m.wires['in2'][0], m.instances['and_inst'].ports['B'][0])
    m.connect(m.wires['wire_and'][0], m.instances['and_inst'].ports['Y'][0])
    m.connect(m.wires['in3'][0], m.instances['or_inst'].ports['A'][0])
    m.connect(m.wires['in4'][0], m.instances['or_inst'].ports['B'][0])
    m.connect(m.wires['wire_or'][0], m.instances['or_inst'].ports['Y'][0])
    m.connect(m.wires['wire_and'][0], m.instances['xor_inst'].ports['A'][0])
    m.connect(m.wires['wire_or'][0], m.instances['xor_inst'].ports['B'][0])
    m.connect(m.wires['wire_xor'][0], m.instances['xor_inst'].ports['Y'][0])
    m.connect(m.wires['wire_xor'][0], m.instances['not_inst'].ports['A'][0])
    m.connect(m.wires['out'][0], m.instances['not_inst'].ports['Y'][0])
    m.connect(m.wires['clk'][0], m.instances['dff_inst'].ports['CLK'][0])
    m.connect(m.wires['rst'][0], m.instances['dff_inst'].ports['RST'][0])
    m.instances['dff_inst'].tie_port('EN', index=0, sig_value='1')
    m.connect(m.wires['wire_xor'][0], m.instances['dff_inst'].ports['D'][0])
    m.connect(m.wires['out_ff'][0], m.instances['dff_inst'].ports['Q'][0])
    return m


def modified_module() -> Module:
    module = connected_module()

    module.create_wire('wire_xor2')
    module.create_wire('wire_not2')
    module.add_instance(XorGate(raw_path=f'{module.name}.xor2_inst'))
    module.add_instance(NotGate(raw_path=f'{module.name}.not2_inst'))

    module.connect(module.wires['out'][0], module.instances['xor2_inst'].ports['A'][0])
    module.connect(module.wires['wire_xor2'][0], module.instances['xor2_inst'].ports['Y'][0])
    module.connect(module.wires['wire_xor2'][0], module.instances['not2_inst'].ports['A'][0])

    # Dangling, not connected to inputs or outputs
    module.create_wire('wire_xor3')
    module.add_instance(XorGate(raw_path=f'{module.name}.xor3_inst'))
    module.add_instance(NotGate(raw_path=f'{module.name}.not3_inst'))

    module.connect(module.wires['wire_xor3'][0], module.instances['xor3_inst'].ports['Y'][0])
    module.connect(module.wires['wire_xor3'][0], module.instances['not3_inst'].ports['A'][0])

    return module


def simple_circuit() -> Circuit:
    c = Circuit(name='test_circuit')
    m1 = Module(raw_path='m1')
    m1.create_wire('w1')
    m1.create_wire('w2')
    m1.create_wire('w3')

    m1.connect(WirePath(raw='m1.w1'), m1.create_port('A', direction=PortDirection.IN))
    m1.connect(WirePath(raw='m1.w2'), m1.create_port('B', direction=PortDirection.IN))
    m1.connect(WirePath(raw='m1.w3'), m1.create_port('Y', direction=PortDirection.OUT))

    i1 = Instance(raw_path='m1.and_inst', instance_type='and', is_primitive=True)
    i1.connect('A', WireSegmentPath(raw='m1.w1.ws1'), direction=PortDirection.IN)
    i1.connect('B', WireSegmentPath(raw='m1.w2.ws1'), direction=PortDirection.IN)
    i1.connect('Y', WireSegmentPath(raw='m1.w3.ws1'), direction=PortDirection.IN)

    c.add_module(m1)
    return c


def connected_circuit() -> Circuit:
    c = Circuit(name='test_circuit')
    c.creator = 'SomeCreator'
    cm = connected_module()
    c.add_module(cm)

    cm_wrapper = Module(raw_path='wrapper')

    cm_wrapper.create_wire('in1')
    cm_wrapper.create_wire('in2')
    cm_wrapper.create_wire('in3')
    cm_wrapper.create_wire('in4')
    cm_wrapper.create_wire('clk')
    cm_wrapper.create_wire('rst')
    cm_wrapper.create_wire('out')
    cm_wrapper.create_wire('out_ff')

    cm_wrapper.connect(WirePath(raw=f'{cm_wrapper.name}.in1'), cm_wrapper.create_port('in1', PortDirection.IN))
    cm_wrapper.connect(WirePath(raw=f'{cm_wrapper.name}.in2'), cm_wrapper.create_port('in2', PortDirection.IN))
    cm_wrapper.connect(WirePath(raw=f'{cm_wrapper.name}.in3'), cm_wrapper.create_port('in3', PortDirection.IN))
    cm_wrapper.connect(WirePath(raw=f'{cm_wrapper.name}.in4'), cm_wrapper.create_port('in4', PortDirection.IN))
    cm_wrapper.connect(WirePath(raw=f'{cm_wrapper.name}.clk'), cm_wrapper.create_port('clk', PortDirection.IN))
    cm_wrapper.connect(WirePath(raw=f'{cm_wrapper.name}.rst'), cm_wrapper.create_port('rst', PortDirection.IN))
    cm_wrapper.connect(WirePath(raw=f'{cm_wrapper.name}.out'), cm_wrapper.create_port('out', PortDirection.OUT))
    cm_wrapper.connect(WirePath(raw=f'{cm_wrapper.name}.out_ff'), cm_wrapper.create_port('out_ff', PortDirection.OUT))

    cm_wrapper.create_instance(cm, 'I_cm')
    i_cm = cm_wrapper.instances['I_cm']

    cm_wrapper.connect(cm_wrapper.wires['in1'][0], i_cm.ports['in1'][0])
    cm_wrapper.connect(cm_wrapper.wires['in2'][0], i_cm.ports['in2'][0])
    cm_wrapper.connect(cm_wrapper.wires['in3'][0], i_cm.ports['in3'][0])
    cm_wrapper.connect(cm_wrapper.wires['in4'][0], i_cm.ports['in4'][0])
    cm_wrapper.connect(cm_wrapper.wires['clk'][0], i_cm.ports['clk'][0])
    cm_wrapper.connect(cm_wrapper.wires['rst'][0], i_cm.ports['rst'][0])
    cm_wrapper.connect(cm_wrapper.wires['out'][0], i_cm.ports['out'][0])
    cm_wrapper.connect(cm_wrapper.wires['out_ff'][0], i_cm.ports['out_ff'][0])
    c.add_module(cm_wrapper)
    c.set_top(cm_wrapper)
    return c
