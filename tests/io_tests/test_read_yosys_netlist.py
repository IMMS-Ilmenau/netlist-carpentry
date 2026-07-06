import copy
import os
import sys

from netlist_carpentry.core.enums.signal import Signal
from netlist_carpentry.io.read.yosys.netlist_types import YosysData, YosysModule

sys.path.append('.')

import pytest
from utils import save_results

from netlist_carpentry import WIRE_SEGMENT_0, WIRE_SEGMENT_1, WIRE_SEGMENT_X, read
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.enums.direction import Direction
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.io.read.yosys.netlist_reader import YosysNetlistReader as YNR
from netlist_carpentry.io.write.py2v import P2VTransformer as P2V
from netlist_carpentry.utils.gate_lib import ADFF, DFF, Adder


@pytest.fixture(scope='function')
def simple_reader() -> YNR:
    read('tests/files/simpleAdder.v', top='simpleAdder', verbose=True)  # To generate the JSON file
    return YNR('tests/files/simpleAdder.json')


@pytest.fixture(scope='function')
def hierarchical_reader() -> YNR:
    read(['tests/files/adderWrapper.v', 'tests/files/simpleAdder.v'], top='adderWrapper', out='tests/files/')  # To generate the JSON file
    return YNR('tests/files/adderWrapper.json')


@pytest.fixture(scope='function')
def escaped_identifier_reader() -> YNR:
    read('tests/files/escaped_identifiers.v', top='weirdName--', out='tests/files/')  # To generate the JSON file
    return YNR('tests/files/escaped_identifiers.json')


def test_reader_init(simple_reader: YNR) -> None:
    assert simple_reader.net_number_mapping == {}
    assert simple_reader.module_name_mapping == {}
    assert simple_reader.module_definitions == {0} - {0}  # Funny eyes <=> empty set
    assert simple_reader.module_instantiations == {0} - {0}  # Funny eyes <=> empty set
    assert simple_reader.module_definitions_and_instances_match

    simple_reader._module_definitions = {'foo', 'bar'}
    simple_reader._module_instantiations = {'foo', 'baz'}

    assert simple_reader.undefined_modules == {'baz'}
    assert simple_reader.uninstantiated_modules == {'bar'}
    assert not simple_reader.module_definitions_and_instances_match

    assert simple_reader.circuit is None


def test_adder_netlist_dict(simple_reader: YNR) -> None:
    nl_dict = simple_reader.read()

    assert len(nl_dict) == 2
    assert 'creator' in nl_dict
    assert len(nl_dict.modules) == 1

    adder = nl_dict.modules['simpleAdder']
    assert len(adder.attributes) == 3
    assert len(adder.ports) == 5
    assert len(adder.cells) == 2
    assert len(adder.netnames) == 6
    assert '§0§out§8§0§' in adder.netnames


def test_preprocess_dict(simple_reader: YNR) -> None:
    given_dict = {
        'modules': {
            'adder': {
                'cells': {
                    '$some_cell$/path/to/src/file.v:420$69': {},
                    r"§paramod\simpleAdder\WIDTH=s32'00000100": {'type': r"§paramod\simpleAdder\WIDTH=s32'00000100"},
                },
            },
            r"§paramod\simpleAdder\WIDTH=s32'00000100": {},
        }
    }
    target_dict = YosysData(
        **{
            'modules': {
                'adder': {
                    'cells': {'some_cell§file§v§420§69': {}, '§simpleAdder§WIDTH§4': {'type': '§simpleAdder§WIDTH§4'}},
                },
                '§simpleAdder§WIDTH§4': {},
            }
        }
    )
    found_dict = simple_reader._preprocess_dict(YosysData(**given_dict))

    assert target_dict == found_dict


def test_preprocess_dict_escaped_identifiers(escaped_identifier_reader: YNR) -> None:
    found_dict = escaped_identifier_reader.read().modules
    assert 'subModule§1§' in found_dict
    assert 'weirdName§§' in found_dict
    assert '§0input§§' in found_dict['weirdName§§'].ports
    assert '§out§put' in found_dict['weirdName§§'].ports
    assert 'In§tance§§§§§' in found_dict['weirdName§§'].cells
    assert '§0input§§' in found_dict['weirdName§§'].netnames
    assert '§out§put' in found_dict['weirdName§§'].netnames
    assert 'someWire§§' in found_dict['weirdName§§'].netnames


def test_simplify_module_name(simple_reader: YNR) -> None:
    assert simple_reader.module_name_mapping == {}
    assert simple_reader.simplify_module_name('some_module_name') == 'some_module_name'
    assert simple_reader.module_name_mapping == {'some_module_name': 'some_module_name'}

    assert simple_reader.simplify_module_name(r'§paramod§simpleAdder§WIDTH§s32§00000000000000000000000000000100') == '§simpleAdder§WIDTH§4'
    assert simple_reader.module_name_mapping == {
        'some_module_name': 'some_module_name',
        '§simpleAdder§WIDTH§4': r'§paramod§simpleAdder§WIDTH§s32§00000000000000000000000000000100',
    }

    assert simple_reader.simplify_module_name('§some.weird-module!name') == '§some§weird§module§name'
    assert simple_reader.module_name_mapping == {
        'some_module_name': 'some_module_name',
        '§simpleAdder§WIDTH§4': r'§paramod§simpleAdder§WIDTH§s32§00000000000000000000000000000100',
        '§some§weird§module§name': '§some.weird-module!name',
    }

    with pytest.raises(KeyError):
        # Simplified name was already created previously
        simple_reader.simplify_module_name('§some.weird-module!name') == '§some§weird§module§name'


def test_adder_netlist_transform_to_circuit(simple_reader: YNR) -> None:
    circuit = simple_reader.transform_to_circuit()
    assert simple_reader.circuit is not None
    assert simple_reader.circuit == circuit

    assert isinstance(circuit, Circuit)
    assert len(circuit.modules) == 1
    assert 'simpleAdder' in circuit.modules
    adder = circuit['simpleAdder']
    assert len(adder.metadata.yosys) == 3
    assert len(adder.ports) == 5
    assert len(adder.instances) == 2
    assert len(adder.wires) == 6

    assert circuit.top_name == 'simpleAdder'

    assert '§add' in adder.instances_by_types
    add = adder.instances_by_types['§add'][0]
    assert isinstance(add, Adder)
    assert len(add.parameters) == 5
    assert add.parameters.A_SIGNED == 0
    assert add.parameters.A_WIDTH == 8
    assert add.parameters.B_SIGNED == 0
    assert add.parameters.B_WIDTH == 8
    assert add.parameters.Y_WIDTH == 9

    assert len(add.metadata.yosys) == 1

    assert len(add.ports) == 3
    assert add.ports['A'].width == 8
    assert add.ports['B'].width == 8
    assert add.ports['Y'].width == 9
    assert add.ports['A'].direction == Direction.IN
    assert add.ports['B'].direction == Direction.IN
    assert add.ports['Y'].direction == Direction.OUT

    assert '§adff' in adder.instances_by_types
    dff = adder.instances_by_types['§adff'][0]
    assert isinstance(dff, DFF)
    assert len(dff.parameters) == 4
    assert dff.parameters.RST_POLARITY == Signal.HIGH
    assert dff.parameters.RST_VALUE == 0
    assert dff.parameters.CLK_POLARITY == Signal.HIGH
    assert dff.parameters.WIDTH == 9

    assert len(dff.metadata.yosys) == 1

    assert len(dff.ports) == 4
    assert dff.ports['D'].width == 9
    assert dff.ports['CLK'].width == 1
    assert dff.ports['RST'].width == 1
    assert dff.ports['Q'].width == 9
    assert dff.ports['D'].direction == Direction.IN
    assert dff.ports['CLK'].direction == Direction.IN
    assert dff.ports['RST'].direction == Direction.IN
    assert dff.ports['Q'].direction == Direction.OUT

    assert add.ports['Y'][0].ws_path == adder.wires['§0§out§8§0§'][0].path
    assert dff.ports['D'][0].ws_path == adder.wires['§0§out§8§0§'][0].path


def test_adder_netlist_transform_to_circuit_name(simple_reader: YNR) -> None:
    c = simple_reader.transform_to_circuit('FOO')

    assert c.name == 'FOO'


def test_populate_circuit_empty_module(simple_reader: YNR) -> None:
    c = Circuit(name='test')
    simple_reader._populate_circuit({'test_module': YosysModule()}, c)

    assert c.module_count == 1
    assert c.top_name == ''


def test_build_wires(simple_reader: YNR) -> None:
    m = Module(name='simpleAdder')

    m1 = copy.deepcopy(m)
    simple_reader._build_wires(m1, YosysModule())
    assert m == m1

    with pytest.raises(AttributeError):
        simple_reader._build_wires(m, {'netnames': {'in2': {'attributes': {'src': 'some_src'}}, 'out': {'attributes': {'src': 'some_src'}}}})

    simple_reader._build_wires(
        m,
        YosysModule(
            **{
                'netnames': {
                    'in2': {'bits': [12, 13], 'attributes': {'src': 'simpleAdder.v:5.22-5.25'}},
                    'out': {'bits': [20, 21, 22], 'attributes': {'src': 'simpleAdder.v:6.22-6.25'}},
                }
            },
        ),
    )

    assert len(m.wires) == 2
    assert m.wires['in2'].width == 2
    assert m.wires['in2'].metadata.yosys == {'src': 'simpleAdder.v:5.22-5.25'}
    assert m.wires['out'].width == 3
    assert m.wires['out'].metadata.yosys == {'src': 'simpleAdder.v:6.22-6.25'}

    assert simple_reader.net_number_mapping['simpleAdder'][12] == WireSegmentPath(raw='simpleAdder.in2.0')
    assert simple_reader.net_number_mapping['simpleAdder'][13] == WireSegmentPath(raw='simpleAdder.in2.1')
    assert simple_reader.net_number_mapping['simpleAdder'][20] == WireSegmentPath(raw='simpleAdder.out.0')
    assert simple_reader.net_number_mapping['simpleAdder'][21] == WireSegmentPath(raw='simpleAdder.out.1')
    assert simple_reader.net_number_mapping['simpleAdder'][22] == WireSegmentPath(raw='simpleAdder.out.2')


def test_build_port(simple_reader: YNR) -> None:
    m = Module(name='simpleAdder')
    with pytest.raises(AttributeError):
        simple_reader.net_number_mapping[m.name] = {}
        simple_reader._build_ports(m, YosysModule(**{'ports': {'in2': {'direction': 'input'}, 'out': {'direction': 'output'}}}))

    m = Module(name='simpleAdder')
    with pytest.raises(AttributeError):
        simple_reader.net_number_mapping[m.name] = {}
        simple_reader._build_ports(
            m, YosysModule(**{'ports': {'in2': {'direction': 'input', 'bits': [12, 13]}, 'out': {'direction': 'output', 'bits': [20, 21, 22]}}})
        )

    m1 = copy.deepcopy(m)
    simple_reader._build_ports(m1, YosysModule())
    assert m == m1

    m = Module(name='simpleAdder')
    simple_reader._build_wires(m, YosysModule(**{'netnames': {'in2': {'bits': [12, 13]}, 'out': {'bits': [20, 21, 22]}}}))
    simple_reader._build_ports(
        m, YosysModule(**{'ports': {'in2_p': {'direction': 'input', 'bits': [12, 13]}, 'out_p': {'direction': 'output', 'bits': [20, 21, 22]}}})
    )

    assert len(m.ports) == 2
    assert m.ports['in2_p'].direction == Direction.IN
    assert m.ports['in2_p'].width == 2
    assert m.ports['in2_p'][0].ws_path.raw == 'simpleAdder.in2.0'
    assert m.ports['in2_p'][1].ws_path.raw == 'simpleAdder.in2.1'
    assert m.wires['in2'][0].port_segments[0].raw_path == 'simpleAdder.in2_p.0'
    assert m.wires['in2'][1].port_segments[0].raw_path == 'simpleAdder.in2_p.1'

    assert m.ports['out_p'].direction == Direction.OUT
    assert m.ports['out_p'].width == 3
    assert m.ports['out_p'][0].ws_path.raw == 'simpleAdder.out.0'
    assert m.ports['out_p'][1].ws_path.raw == 'simpleAdder.out.1'
    assert m.ports['out_p'][2].ws_path.raw == 'simpleAdder.out.2'
    assert m.wires['out'][0].port_segments[0].raw_path == 'simpleAdder.out_p.0'
    assert m.wires['out'][1].port_segments[0].raw_path == 'simpleAdder.out_p.1'
    assert m.wires['out'][2].port_segments[0].raw_path == 'simpleAdder.out_p.2'


def test_build_port_const(simple_reader: YNR) -> None:
    m = Module(name='simpleAdder')
    simple_reader.net_number_mapping[m.name] = {}
    simple_reader._build_ports(
        m, YosysModule(**{'ports': {'in2_p': {'direction': 'input', 'bits': ['0']}, 'out_p': {'direction': 'output', 'bits': ['1', 'x']}}})
    )

    assert len(m.ports['in2_p']) == 1
    assert m.ports['in2_p'][0].ws_path == WIRE_SEGMENT_0.path
    assert len(m.ports['out_p']) == 2
    assert m.ports['out_p'][0].ws_path == WIRE_SEGMENT_1.path
    assert m.ports['out_p'][1].ws_path == WIRE_SEGMENT_X.path


def test_build_instances(simple_reader: YNR) -> None:
    m = Module(name='simpleAdder')

    # TODO add pytest.raises cases
    m1 = copy.deepcopy(m)
    simple_reader._build_instances(m1, YosysModule())
    assert m == m1

    wires = {
        'netnames': {
            '§0§out§8§0§': {'bits': [29, 30, 31, 32, 33, 34, 35, 36, 37]},
            'clk': {'bits': [2]},
            'in1': {'bits': [4, 5, 6, 7, 8, 9, 10, 11]},
            'in2': {'bits': [12, 13, 14, 15, 16, 17, 18, 19]},
            'out': {'bits': [20, 21, 22, 23, 24, 25, 26, 27, 28]},
            'rst': {'bits': [3]},
        }
    }
    instances = {
        'cells': {
            '§add§simpleAdder.v:13§2': {
                'hide_name': 1,
                'type': '$add',
                'parameters': {
                    'A_SIGNED': '00000000000000000000000000000000',
                    'A_WIDTH': '00000000000000000000000000001000',
                    'B_SIGNED': '00000000000000000000000000000001',
                    'B_WIDTH': '00000000000000000000000000001000',
                    'Y_WIDTH': '00000000000000000000000000001001',
                },
                'attributes': {'src': 'simpleAdder.v:13.15-13.24'},
                'port_directions': {'A': 'input', 'B': 'input', 'Y': 'output'},
                'connections': {
                    'A': [4, 5, 6, 7, 8, 9, 10, 11],
                    'B': [12, 13, 14, 15, 16, 17, 18, 19],
                    'Y': [29, 30, 31, 32, 33, 34, 35, 36, 37],
                },
            },
            '$procdff$3': {
                'hide_name': 1,
                'type': '$adff',
                'parameters': {'ARST_POLARITY': '1', 'ARST_VALUE': '000000000', 'CLK_POLARITY': '1', 'WIDTH': '00000000000000000000000000001001'},
                'attributes': {'src': 'simpleAdder.v:8.1-15.4'},
                'port_directions': {'ARST': 'input', 'CLK': 'input', 'D': 'input', 'Q': 'output'},
                'connections': {'ARST': [3], 'CLK': [2], 'D': [29, 30, 31, 32, 33, 34, 35, 36, 37], 'Q': [20, 21, 22, 23, 24, 25, 26, 27, 28]},
            },
        }
    }

    insts = YosysModule(**instances)
    insts.clean()
    ws = YosysModule(**wires)
    ws.clean()
    with pytest.raises(AttributeError):
        simple_reader.net_number_mapping[m.name] = {}
        simple_reader._build_instances(m, insts)

    m = Module(name='simpleAdder')
    simple_reader._build_wires(m, ws)
    simple_reader._build_instances(m, insts)
    assert len(m.instances) == 2
    assert '§add' in m.instances_by_types
    assert '§adff' in m.instances_by_types
    add = m.instances_by_types['§add'][0]
    adff = m.instances_by_types['§adff'][0]

    assert isinstance(add, Adder)
    assert len(add.parameters) == 5
    assert add.parameters.A_SIGNED is False
    assert add.parameters.A_WIDTH == 8
    assert add.parameters.B_SIGNED is True
    assert add.parameters.A_WIDTH == 8
    assert add.parameters.Y_WIDTH == 9
    assert len(add.ports) == 3
    assert add.input_ports == (add.ports['A'], add.ports['B'])
    assert add.ports['A'].width == 8
    assert add.ports['A'].is_instance_port
    ps = [add.ports['A'][i].raw_ws_path == f'simpleAdder.in1.{i}' for i in add.ports['A'].segments]
    assert all(ps)
    assert add.ports['B'].width == 8
    assert add.ports['B'].is_instance_port
    assert all(add.ports['B'][i].raw_ws_path == f'simpleAdder.in2.{i}' for i in add.ports['B'].segments)
    assert add.ports['Y'].width == 9
    assert add.ports['Y'].is_instance_port
    assert all(add.ports['Y'][i].raw_ws_path == f'simpleAdder.§0§out§8§0§.{i}' for i in add.ports['Y'].segments)
    for i in range(8):
        assert add.ports['A'][i] in m.wires['in1'][i].port_segments
        assert add.ports['B'][i] in m.wires['in2'][i].port_segments
        assert add.ports['Y'][i] in m.wires['§0§out§8§0§'][i].port_segments

    assert isinstance(adff, ADFF)
    assert len(adff.parameters) == 4
    assert adff.parameters.RST_POLARITY == Signal.HIGH
    assert adff.parameters.RST_VALUE == 0
    assert adff.parameters.CLK_POLARITY == Signal.HIGH
    assert adff.parameters.WIDTH == 9
    assert len(adff.ports) == 4  # 4 Ports from dict
    assert adff.input_ports == (adff.ports['D'], adff.ports['CLK'], adff.ports['RST'])
    assert adff.output_port == adff.ports['Q']
    assert adff.ports['D'].width == 9
    assert adff.ports['D'].is_instance_port
    assert all(adff.ports['D'][i].raw_ws_path == f'simpleAdder.§0§out§8§0§.{i}' for i in adff.ports['D'].segments)
    assert adff.ports['CLK'].width == 1
    assert adff.ports['CLK'].is_instance_port
    assert all(adff.ports['CLK'][i].raw_ws_path == f'simpleAdder.clk.{i}' for i in adff.ports['CLK'].segments)
    assert adff.ports['RST'].width == 1
    assert adff.ports['RST'].is_instance_port
    assert all(adff.ports['RST'][i].raw_ws_path == f'simpleAdder.rst.{i}' for i in adff.ports['RST'].segments)
    assert adff.ports['Q'].width == 9
    assert adff.ports['Q'].is_instance_port
    assert all(adff.ports['Q'][i].raw_ws_path == f'simpleAdder.out.{i}' for i in adff.ports['Q'].segments)


def test_instance_index_offset(hierarchical_reader: YNR) -> None:
    circuit = hierarchical_reader.transform_to_circuit()
    in1 = circuit.top.wires['in1']
    in2 = circuit.top.wires['in2']
    assert set(in1.segments.keys()) == {1, 2, 3, 4}
    assert set(in2.segments.keys()) == {4, 5, 6, 7}

    assert in1.msb_first
    assert not in1.lsb_first
    assert not in2.msb_first
    assert in2.lsb_first

    in1 = circuit.top.ports['in1']
    in2 = circuit.top.ports['in2']
    assert set(in1.segments.keys()) == {1, 2, 3, 4}
    assert set(in2.segments.keys()) == {4, 5, 6, 7}

    assert in1.msb_first
    assert not in1.lsb_first
    assert not in2.msb_first
    assert in2.lsb_first


def test_hierarchical_circuit(hierarchical_reader: YNR) -> None:
    c = hierarchical_reader.transform_to_circuit('hierarchical')

    assert len(c.modules) == 2
    assert hierarchical_reader.module_definitions == {'§simpleAdder§WIDTH§4', 'adderWrapper'}
    assert hierarchical_reader.module_instantiations == {'§simpleAdder§WIDTH§4'}
    assert hierarchical_reader.module_definitions_and_instances_match

    assert '§simpleAdder§WIDTH§4' in c.modules
    assert 'adderWrapper' in c.modules

    sadder = c['§simpleAdder§WIDTH§4']
    assert len(sadder.ports) == 5
    assert len(sadder.instances) == 2
    assert len(sadder.wires) == 6
    assert len(sadder.parameters) == 1

    # assert '§nc_0' in sadder.wires
    assert 'clk' in sadder.wires
    assert 'in1' in sadder.wires
    assert 'in2' in sadder.wires
    assert 'out' in sadder.wires
    assert 'rst' in sadder.wires

    hadder = c['adderWrapper']
    assert len(hadder.ports) == 5
    assert len(hadder.instances) == 2
    assert len(hadder.wires) == 6
    assert len(hadder.parameters) == 1

    assert 'internal_out' in hadder.wires
    assert 'clk' in hadder.wires
    assert 'in1' in hadder.wires
    assert 'in2' in hadder.wires
    assert 'out' in hadder.wires
    assert 'rst' in hadder.wires

    assert '§reduce_or' in hadder.instances_by_types
    assert 'adder' in hadder.instances

    p2v = P2V()
    for m in c:
        save_results(p2v.module2v(m), 'v', m.name)
    save_results(p2v.circuit2v(c), 'v', c.name)


def test_deprecation_warnings() -> None:
    warn_str = "Importing 'netlist_carpentry.io.read.yosys_netlist_types' is deprecated and will be removed in v1.0.0. This module has been renamed and moved to 'netlist_carpentry.io.read.yosys.netlist_types'! Please use 'import netlist_carpentry.io.read.yosys.netlist_types' instead."
    with pytest.warns(DeprecationWarning):
        import netlist_carpentry.io.read.yosys_netlist_types as tmp

        tmp

    warn_str = "Importing 'netlist_carpentry.io.read.yosys_netlist' is deprecated and will be removed in v1.0.0. This module has been renamed and moved to 'netlist_carpentry.io.read.yosys.netlist_reader'! Please use 'import netlist_carpentry.io.read.yosys.netlist_reader' instead."
    with pytest.warns(DeprecationWarning, match=warn_str):
        import netlist_carpentry.io.read.yosys_netlist as tmp

        tmp


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
