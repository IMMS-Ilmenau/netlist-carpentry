import os
import sys

from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire_segment import (
    WIRE_SEGMENT_0,
    WIRE_SEGMENT_1,
    WIRE_SEGMENT_X,
    WIRE_SEGMENT_Z,
)

sys.path.append('.')

import pytest

from netlist_carpentry.api.write.py2v import P2VTransformer
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath as WSPath
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.utils.gate_lib import AndGate, LibUtils
from tests.utils import save_results


@pytest.fixture
def writer() -> P2VTransformer:
    return P2VTransformer()


@pytest.fixture
def standard_module() -> Module:
    from tests.utils import empty_module as esm

    m = esm()
    m.create_wire('test_port')
    m.connect(m.create_wire('test_wire'), m.create_port('test_port', PortDirection.IN_OUT))
    m.add_instance(AndGate(raw_path='test_module1.test_instance', module=m))
    return m


def test_save_circuit2v(writer: P2VTransformer) -> None:
    from tests.utils import connected_circuit

    path = 'tests/files/gen/save_circuit2v.v'
    if os.path.exists(path):
        os.remove(path)
    c = connected_circuit()
    writer.save_circuit2v(path, c)
    assert os.path.exists(path)
    m_w = writer.module2v(c['wrapper'])
    m_t = writer.module2v(c['test_module1'])
    with open(path) as f:
        v = f.read()
    assert m_t + '\n\n\n' + m_w in v
    os.remove(path)


def test_circuit2v(writer: P2VTransformer) -> None:
    from tests.utils import connected_circuit

    LibUtils.change_current_module(Module(raw_path='SomeModule'))
    c = connected_circuit()
    v = writer.circuit2v(c)
    m_w = writer.module2v(c['wrapper'])
    m_t = writer.module2v(c['test_module1'])
    assert v == m_t + '\n\n\n' + m_w
    save_results(v, 'v')


def test_wire2v(writer: P2VTransformer) -> None:
    from tests.utils import connected_module, standard_wire, wire_4b

    m = connected_module()
    sw = standard_wire()
    w4 = wire_4b()
    m.add_wire(sw)
    m.add_wire(w4)
    target_wcode = 'wire\t\twire1;'
    found_wcode = writer.wire2v(m, sw)
    assert target_wcode == found_wcode

    sw[1].raw_path = ''
    writer.wire2v(m, sw)
    assert writer._constant_wire_segments == {'test_module1': {'test_module1.wire1.1': WIRE_SEGMENT_X}}

    w4[1].raw_path = '0'
    writer.wire2v(m, w4)
    assert writer._constant_wire_segments == {'test_module1': {'test_module1.wire1.1': WIRE_SEGMENT_X, 'test_module1.wire4b.1': WIRE_SEGMENT_0}}

    target_wcode = 'wire [1:4]\twire4b;'
    found_wcode = writer.wire2v(m, w4)
    assert target_wcode == found_wcode

    wreg = m.wires['out_ff']
    target_wcode = 'reg \t\tout_ff;'
    found_wcode = writer.wire2v(m, wreg)
    assert target_wcode == found_wcode


def test_wire_is_const(writer: P2VTransformer) -> None:
    assert writer._get_const_from_wseg_path('') == "1'bx"
    assert writer._get_const_from_wseg_path('X') == "1'bx"
    assert writer._get_const_from_wseg_path('Z') == "1'bz"
    assert writer._get_const_from_wseg_path('0') == "1'b0"
    assert writer._get_const_from_wseg_path('1') == "1'b1"


def test_const_wire_assigns(writer: P2VTransformer) -> None:
    from tests.utils import empty_module

    m = empty_module()
    m.create_wire('w', width=6)
    m.wires['w'][0].raw_path = 'test_module1.w.0'  # Only bit not constant!
    m.wires['w'].segments[1] = WIRE_SEGMENT_0
    m.wires['w'].segments[2] = WIRE_SEGMENT_1
    m.wires['w'].segments[3] = WIRE_SEGMENT_Z
    m.wires['w'].segments[4] = WIRE_SEGMENT_X
    writer._constant_wire_segments = {
        'test_module1': {
            'test_module1.w.1': m.wires['w'][1],
            'test_module1.w.2': m.wires['w'][2],
            'test_module1.w.3': m.wires['w'][3],
            'test_module1.w.4': m.wires['w'][4],
        }
    }
    target_str = "\t// Constant Wires\n\t\tassign w[1]\t= 1'b0;\n\t\tassign w[2]\t= 1'b1;\n\t\tassign w[3]\t= 1'bz;\n\t\tassign w[4]\t= 1'bx;\n"
    found_str = writer._constant_wires2v(m)

    assert target_str == found_str


def test_port2v(writer: P2VTransformer) -> None:
    from tests.utils import empty_module, standard_port_in, standard_port_out

    m = empty_module()
    m.create_wire('test_port1')
    m.create_wire('test_port2', width=2)
    target_pcode = 'input\twire\t\t\ttest_port1'
    found_pcode = writer.port2v(m, standard_port_in())

    assert target_pcode == found_pcode

    target_pcode = 'output\twire\t[0:1]\ttest_port2'
    found_pcode = writer.port2v(m, standard_port_out())

    assert target_pcode == found_pcode

    m.create_wire('test_port3')
    p = Port(raw_path='test_module.test_port3', direction=PortDirection.OUT, msb_first=False, module_or_instance=m)
    p.create_port_segment(2).set_ws_path('test_module.test_port3.0')
    p.create_port_segment(3).set_ws_path('test_module.test_port3.0')
    m.add_port(p)

    target_pcode = 'output\twire\t[2:3]\ttest_port3'
    found_pcode = writer.port2v(m, p)

    assert target_pcode == found_pcode


def test_module2v_empty(writer: P2VTransformer) -> None:
    from tests.utils import empty_module

    target_mcode = 'module test_module1();\n\nendmodule'
    found_mcode = writer.module2v(empty_module())
    save_results(found_mcode, 'v')

    assert target_mcode == found_mcode


def test_module2v(writer: P2VTransformer, standard_module: Module) -> None:
    from tests.utils import standard_instance_with_ports, wire_1b, wire_4b

    inst = standard_instance_with_ports()
    inst.ports['PortC'][0].set_ws_path('test_module1.wire1b.1')
    standard_module.add_instance(inst)
    wire = wire_1b()
    standard_module.add_wire(wire)
    wire = wire_4b()
    standard_module.add_wire(wire)
    standard_module.create_wire('out_assign')
    standard_module.connect(wire[1], standard_module.create_port('out_assign', PortDirection.OUT)[0])
    standard_module.parameters['foo'] = 'bar'
    standard_module.parameters['baz'] = 42
    standard_module.instances['test_instance'].modify_connection('Y', standard_module.wires['wire1b'][1].path)
    # TODO fix code for primitive instance
    target_mcode = 'module test_module1\n\t#(\n\t\tparameter foo = "bar",\n\t\tparameter baz = 42\n\t)\n\t(\n\t\tinout\twire\t\t\ttest_port,\n\t\toutput\twire\t\t\tout_assign\n\t);\n\t// Wire Definitions\n\t\twire\t\ttest_wire;\n\t\twire\t\twire1b;\n\t\twire [1:4]\twire4b;\n\n\t// Primitive Gates and Submodule Instances\n\t\tassign wire1b = 1\'bx & 1\'bx;\n\n\t\ttest_instance_type test_instance2(\n\t\t\t.PortA(wire4b[1]),\n\t\t\t.PortB({wire4b[1], wire4b[2], wire4b[3:2]}),\n\t\t\t.PortC(wire1b)\n\t\t);\n\t// Output Wires\n\t\tassign out_assign\t= wire4b[1];\n\t\tassign test_port\t= test_wire;\n\nendmodule'
    found_mcode = writer.module2v(standard_module)
    save_results(found_mcode, 'v')

    assert target_mcode == found_mcode


def test_module2v_id_replacement(writer: P2VTransformer) -> None:
    from tests.utils import empty_module

    m = empty_module()
    m.raw_path = '§' + m.raw_path
    m.create_instance(Module(raw_path='§some_type'), '§some_name')
    m.create_wire('§port§1')
    m.create_wire('§port§2')
    m.connect(m.create_wire('§wire§1'), m.create_port('§port§1', PortDirection.IN))
    m.connect(m.create_wire('§wire§2'), m.create_port('§port§2', PortDirection.OUT))
    m.instances['§some_name'].connect('A', WSPath(raw='§test_module1.§wire§1.0'), PortDirection.IN)
    m.instances['§some_name'].connect('Y', WSPath(raw='§test_module1.§wire§2.0'), PortDirection.IN)

    target_str = 'module __test_module1\n\t(\n\t\tinput\twire\t\t\t__port__1,\n\t\toutput\twire\t\t\t__port__2\n\t);\n\t// Wire Definitions\n\t\twire\t\t__wire__1;\n\t\twire\t\t__wire__2;\n\n\t// Primitive Gates and Submodule Instances\n\n\t\t__some_type __some_name(\n\t\t\t.A(__wire__1),\n\t\t\t.Y(__wire__2)\n\t\t);\n\t// Output Wires\n\t\tassign __port__2\t= __wire__2;\n\nendmodule'
    found_str = writer.module2v(m)
    save_results(found_str, 'v')
    assert target_str == found_str


def test_module2v_wire_edge_cases(writer: P2VTransformer) -> None:
    from tests.utils import empty_module

    unconnected_wire = writer.wire_name_and_index_from_str(empty_module(), '')
    assert unconnected_wire == "1'bx"

    unconnected_wire = writer.wire_name_and_index_from_str(empty_module(), 'X')
    assert unconnected_wire == "1'bx"

    unconnected_wire = writer.wire_name_and_index(empty_module(), WIRE_SEGMENT_X.path)
    assert unconnected_wire == "1'bx"

    floating_wire = writer.wire_name_and_index_from_str(empty_module(), 'Z')
    assert floating_wire == "1'bz"

    floating_wire = writer.wire_name_and_index(empty_module(), WIRE_SEGMENT_Z.path)
    assert floating_wire == "1'bz"

    const_wire1 = writer.wire_name_and_index_from_str(empty_module(), '1')
    assert const_wire1 == "1'b1"

    const_wire1 = writer.wire_name_and_index(empty_module(), WIRE_SEGMENT_1.path)
    assert const_wire1 == "1'b1"

    const_wire0 = writer.wire_name_and_index_from_str(empty_module(), '0')
    assert const_wire0 == "1'b0"

    const_wire0 = writer.wire_name_and_index(empty_module(), WIRE_SEGMENT_0.path)
    assert const_wire0 == "1'b0"


def test_instance2v(writer: P2VTransformer, standard_module: Module) -> None:
    standard_module.create_instance(Module(raw_path='some_module'), 'test_module_instance')
    standard_module.create_wire('wireA')
    standard_module.create_wire('wireB')
    standard_module.create_wire('wireC')
    target_mod_inst_str = '\n\t\tsome_module test_module_instance();\n'
    found_mod_inst_str = writer.instance2v(standard_module, standard_module.instances['test_module_instance'])
    assert target_mod_inst_str == found_mod_inst_str

    standard_module.instances['test_instance'].ports.clear()
    standard_module.instances['test_instance'].connect('A', WSPath(raw='test_module1.wireA.0'))
    standard_module.instances['test_instance'].connect('B', WSPath(raw='test_module1.wireB.0'))
    standard_module.instances['test_instance'].connect('Y', WSPath(raw='test_module1.wireC.0'))

    target_mod_inst_str = '\t\tassign wireC = wireA & wireB;\n'
    found_mod_inst_str = writer.instance2v(standard_module, standard_module.instances['test_instance'])
    assert target_mod_inst_str == found_mod_inst_str


def test_simplify_wire_segments(writer: P2VTransformer, standard_module: Module) -> None:
    standard_module.create_wire('wire4', width=4)
    w = standard_module.wires['test_wire']
    w1 = WIRE_SEGMENT_1
    w4 = standard_module.wires['wire4']
    full_wire = [w4[3], w4[2], w4[1], w4[0]]
    assert writer.simplify_wire_segments(standard_module, full_wire) == 'wire4'
    assert writer.simplify_wire_segments(standard_module, full_wire[:3]) == 'wire4[3:1]'
    assert writer.simplify_wire_segments(standard_module, full_wire[1:]) == 'wire4[2:0]'
    assert writer.simplify_wire_segments(standard_module, [w4[3], w4[0]]) == '{wire4[3], wire4[0]}'
    assert writer.simplify_wire_segments(standard_module, [w4[3], w[0], w4[0]]) == '{wire4[3], test_wire, wire4[0]}'
    assert writer.simplify_wire_segments(standard_module, [w4[3], w4[2], w4[1], w[0], w4[2], w4[1], w4[0]]) == '{wire4[3:1], test_wire, wire4[2:0]}'

    assert writer.simplify_wire_segments(standard_module, [w4[3], w4[2], w4[1], w1, w4[0]]) == "{wire4[3:1], 1'b1, wire4[0]}"
    assert writer.simplify_wire_segments(standard_module, [w4[3], w4[2], w4[1], w1, w1, w4[0]]) == "{wire4[3:1], 2'b11, wire4[0]}"


def test_simplify_constant_wire_segments(writer: P2VTransformer) -> None:
    w1 = WIRE_SEGMENT_1
    w0 = WIRE_SEGMENT_0
    wz = WIRE_SEGMENT_Z
    wx = WIRE_SEGMENT_X
    assert writer._simplify_constant_wire_segments([w1]) == "1'b1"
    assert writer._simplify_constant_wire_segments([w1, w1, w1, w1]) == "4'b1111"
    assert writer._simplify_constant_wire_segments([w0, w1, w0, w1]) == "4'b0101"
    assert writer._simplify_constant_wire_segments([wz, wz, w0, w1]) == "4'bzz01"
    assert writer._simplify_constant_wire_segments([wz, wz, wx, wx]) == "4'bzzxx"


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
