import copy
import os
import sys

from netlist_carpentry.core.signal import Signal

sys.path.append('.')

import pytest
from utils import save_results

from netlist_carpentry import CFG, WIRE_SEGMENT_0, WIRE_SEGMENT_1, WIRE_SEGMENT_X, read
from netlist_carpentry.api.read.yosys_netlist import YosysNetlistReader as YNR
from netlist_carpentry.api.write.py2v import P2VTransformer as P2V
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.utils.gate_lib import DFF, Adder


@pytest.fixture
def simple_reader() -> YNR:
    CFG.simplify_escaped_identifiers = True
    read('tests/files/simpleAdder.v', top='simpleAdder')  # To generate the JSON file
    return YNR('tests/files/simpleAdder.json')


@pytest.fixture
def hierarchical_reader() -> YNR:
    read(['tests/files/adderWrapper.v', 'tests/files/simpleAdder.v'], top='adderWrapper', out='tests/files/')  # To generate the JSON file
    return YNR('tests/files/adderWrapper.json')


def test_reader_init(simple_reader: YNR) -> None:
    assert simple_reader.net_number_mapping == {}
    assert simple_reader.module_name_mapping == {}
    assert simple_reader.port_name_mapping == {}
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
    assert len(nl_dict['modules']) == 1

    adder = nl_dict['modules']['simpleAdder']
    assert len(adder['attributes']) == 3
    assert len(adder['ports']) == 5
    assert len(adder['cells']) == 2
    assert len(adder['netnames']) == 6
    # Depending on test order, the escaped identifier may or may not be simplified
    assert '§0§out§8§0§' in adder['netnames'] or not CFG.simplify_escaped_identifiers
    assert '$0\\out[8:0]' in adder['netnames'] or CFG.simplify_escaped_identifiers


def test_preprocess_dict(simple_reader: YNR) -> None:
    given_dict = {
        'modules': {
            'adder': {r"§paramod\simpleAdder\WIDTH=s32'00000100": {'some_key': r"§paramod\simpleAdder\WIDTH=s32'00000100"}},
            r"§paramod\simpleAdder\WIDTH=s32'00000100": {},
        }
    }
    target_dict = {'modules': {'adder': {'§simpleAdder§WIDTH4': {'some_key': '§simpleAdder§WIDTH4'}}, '§simpleAdder§WIDTH4': {}}}
    found_dict = simple_reader._preprocess_dict(given_dict)

    assert target_dict == found_dict


def test_simplify_module_name(simple_reader: YNR) -> None:
    assert simple_reader.module_name_mapping == {}
    assert simple_reader.simplify_module_name('some_module_name') == 'some_module_name'
    assert simple_reader.module_name_mapping == {'some_module_name': 'some_module_name'}

    assert simple_reader.simplify_module_name(r"§paramod\simpleAdder\WIDTH=s32'00000000000000000000000000000100") == '§simpleAdder§WIDTH4'
    assert simple_reader.module_name_mapping == {
        'some_module_name': 'some_module_name',
        '§simpleAdder§WIDTH4': r"§paramod\simpleAdder\WIDTH=s32'00000000000000000000000000000100",
    }

    assert simple_reader.simplify_module_name('§some.weird-module!name') == '§some§weird§module§name'
    assert simple_reader.module_name_mapping == {
        'some_module_name': 'some_module_name',
        '§simpleAdder§WIDTH4': r"§paramod\simpleAdder\WIDTH=s32'00000000000000000000000000000100",
        '§some§weird§module§name': '§some.weird-module!name',
    }

    with pytest.raises(KeyError):
        # Simplified name was already created previously
        simple_reader.simplify_module_name('§some.weird-module!name') == '§some§weird§module§name'


def test_simplify_port_name(simple_reader: YNR) -> None:
    assert simple_reader.port_name_mapping == {}
    assert simple_reader.simplify_port_name('some_port_name', 'module1') == 'some_port_name'
    assert simple_reader.port_name_mapping == {'some_port_name': [('some_port_name', 'module1')]}

    assert simple_reader.simplify_port_name(r'2vector[3:0]port', 'module1.instance1') == '§2vector§3§0§port'
    assert simple_reader.port_name_mapping == {
        'some_port_name': [('some_port_name', 'module1')],
        '§2vector§3§0§port': [(r'2vector[3:0]port', 'module1.instance1')],
    }

    assert simple_reader.simplify_port_name('§some.weird-port!name', 'module1') == '§some§weird§port§name'
    assert simple_reader.port_name_mapping == {
        'some_port_name': [('some_port_name', 'module1')],
        '§2vector§3§0§port': [(r'2vector[3:0]port', 'module1.instance1')],
        '§some§weird§port§name': [('§some.weird-port!name', 'module1')],
    }

    assert simple_reader.simplify_port_name('§some.weird-port!name', 'module1.instance1') == '§some§weird§port§name'
    assert simple_reader.port_name_mapping == {
        'some_port_name': [('some_port_name', 'module1')],
        '§2vector§3§0§port': [(r'2vector[3:0]port', 'module1.instance1')],
        '§some§weird§port§name': [('§some.weird-port!name', 'module1'), ('§some.weird-port!name', 'module1.instance1')],
    }


def test_simplify_instance_name(simple_reader: YNR) -> None:
    assert simple_reader.instance_name_mapping == {}
    simple_reader.simplify_instance_name('adder', 'some_instance_name')
    assert simple_reader.instance_name_mapping == {'adder': {'some_instance_name': 'some_instance_name'}}
    simple_reader.simplify_instance_name('adder', r'\weird§-name')
    assert simple_reader.instance_name_mapping == {'adder': {'some_instance_name': 'some_instance_name', '§weird§§name': r'\weird§-name'}}
    simple_reader.simplify_instance_name('adder', r'\weird§-name2')
    assert simple_reader.instance_name_mapping == {
        'adder': {'some_instance_name': 'some_instance_name', '§weird§§name': r'\weird§-name', '§weird§§name2': r'\weird§-name2'}
    }
    simple_reader.simplify_instance_name('m2', r'1\weird§-name3')
    assert simple_reader.instance_name_mapping == {
        'adder': {'some_instance_name': 'some_instance_name', '§weird§§name': r'\weird§-name', '§weird§§name2': r'\weird§-name2'},
        'm2': {'§1§weird§§name3': r'1\weird§-name3'},
    }
    with pytest.raises(KeyError):
        simple_reader.simplify_instance_name('m2', r'1§weird§-name3')

    simple_reader.simplify_instance_name('m2', r'\weird§-name4')
    assert simple_reader.instance_name_mapping == {
        'adder': {'some_instance_name': 'some_instance_name', '§weird§§name': r'\weird§-name', '§weird§§name2': r'\weird§-name2'},
        'm2': {'§1§weird§§name3': r'1\weird§-name3', '§weird§§name4': r'\weird§-name4'},
    }


def test_simplify_wire_name(simple_reader: YNR) -> None:
    assert simple_reader.wire_name_mapping == {}
    simple_reader.simplify_wire_name('adder', 'some_wire_name')
    assert simple_reader.wire_name_mapping == {'adder': {'some_wire_name': 'some_wire_name'}}
    simple_reader.simplify_wire_name('adder', r'\weird§-name')
    assert simple_reader.wire_name_mapping == {'adder': {'some_wire_name': 'some_wire_name', '§weird§§name': r'\weird§-name'}}
    simple_reader.simplify_wire_name('adder', r'\weird§-name2')
    assert simple_reader.wire_name_mapping == {
        'adder': {'some_wire_name': 'some_wire_name', '§weird§§name': r'\weird§-name', '§weird§§name2': r'\weird§-name2'}
    }
    simple_reader.simplify_wire_name('m2', r'2\weird§-name3')
    assert simple_reader.wire_name_mapping == {
        'adder': {'some_wire_name': 'some_wire_name', '§weird§§name': r'\weird§-name', '§weird§§name2': r'\weird§-name2'},
        'm2': {'§2§weird§§name3': r'2\weird§-name3'},
    }
    with pytest.raises(KeyError):
        simple_reader.simplify_wire_name('m2', r'2\weird§-name3')

    simple_reader.simplify_wire_name('m2', r'\weird§-name4')
    assert simple_reader.wire_name_mapping == {
        'adder': {'some_wire_name': 'some_wire_name', '§weird§§name': r'\weird§-name', '§weird§§name2': r'\weird§-name2'},
        'm2': {'§2§weird§§name3': r'2\weird§-name3', '§weird§§name4': r'\weird§-name4'},
    }


def test_adder_netlist_transform_to_circuit(simple_reader: YNR) -> None:
    CFG.simplify_escaped_identifiers = True
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
    assert add.parameters['A_SIGNED'] == 0
    assert add.parameters['A_WIDTH'] == 8
    assert add.parameters['B_SIGNED'] == 0
    assert add.parameters['B_WIDTH'] == 8
    assert add.parameters['Y_WIDTH'] == 9

    assert len(add.metadata.yosys) == 1

    assert len(add.ports) == 3
    assert add.ports['A'].width == 8
    assert add.ports['B'].width == 8
    assert add.ports['Y'].width == 9
    assert add.ports['A'].direction == PortDirection.IN
    assert add.ports['B'].direction == PortDirection.IN
    assert add.ports['Y'].direction == PortDirection.OUT

    assert '§dff' in adder.instances_by_types
    dff = adder.instances_by_types['§dff'][0]
    assert isinstance(dff, DFF)
    assert len(dff.parameters) == 4
    assert dff.parameters['ARST_POLARITY'] == 1
    assert dff.parameters['ARST_VALUE'] == 0
    assert dff.parameters['CLK_POLARITY'] == 1
    assert dff.parameters['WIDTH'] == 9

    assert len(dff.metadata.yosys) == 1

    assert len(dff.ports) == 5
    assert dff.ports['D'].width == 9
    assert dff.ports['CLK'].width == 1
    assert dff.ports['RST'].width == 1
    assert dff.ports['EN'].width == 1
    assert dff.ports['Q'].width == 9
    assert dff.ports['D'].direction == PortDirection.IN
    assert dff.ports['CLK'].direction == PortDirection.IN
    assert dff.ports['RST'].direction == PortDirection.IN
    assert dff.ports['EN'].direction == PortDirection.IN
    assert dff.ports['Q'].direction == PortDirection.OUT

    assert add.ports['Y'][0].ws_path == adder.wires['§0§out§8§0§'][0].path
    assert dff.ports['D'][0].ws_path == adder.wires['§0§out§8§0§'][0].path


def test_adder_netlist_transform_to_circuit_name(simple_reader: YNR) -> None:
    CFG.simplify_escaped_identifiers = True
    c = simple_reader.transform_to_circuit('FOO')

    assert c.name == 'FOO'


def test_populate_circuit_empty_module(simple_reader: YNR) -> None:
    c = Circuit(name='test')
    simple_reader._populate_circuit({'test_module': {}}, c)

    assert c.module_count == 1
    assert c.top_name == ''


def test_build_wires(simple_reader: YNR) -> None:
    m = Module(raw_path='simpleAdder')

    m1 = copy.deepcopy(m)
    simple_reader._build_wires(m1, {})
    assert m == m1

    with pytest.raises(AttributeError):
        simple_reader._build_wires(m, {'netnames': {'in2': {'attributes': {'src': 'some_src'}}, 'out': {'attributes': {'src': 'some_src'}}}})

    simple_reader._build_wires(
        m,
        {
            'netnames': {
                'in2': {'bits': [12, 13], 'attributes': {'src': 'simpleAdder.v:5.22-5.25'}},
                'out': {'bits': [20, 21, 22], 'attributes': {'src': 'simpleAdder.v:6.22-6.25'}},
            }
        },
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
    m = Module(raw_path='simpleAdder')
    with pytest.raises(AttributeError):
        simple_reader.net_number_mapping[m.name] = {}
        simple_reader._build_ports(m, {'ports': {'in2': {'direction': 'input'}, 'out': {'direction': 'output'}}})

    m = Module(raw_path='simpleAdder')
    with pytest.raises(AttributeError):
        simple_reader.net_number_mapping[m.name] = {}
        simple_reader._build_ports(
            m, {'ports': {'in2': {'direction': 'input', 'bits': [12, 13]}, 'out': {'direction': 'output', 'bits': [20, 21, 22]}}}
        )

    m1 = copy.deepcopy(m)
    simple_reader._build_ports(m1, {})
    assert m == m1

    m = Module(raw_path='simpleAdder')
    simple_reader._build_wires(m, {'netnames': {'in2': {'bits': [12, 13]}, 'out': {'bits': [20, 21, 22]}}})
    simple_reader._build_ports(
        m, {'ports': {'in2_p': {'direction': 'input', 'bits': [12, 13]}, 'out_p': {'direction': 'output', 'bits': [20, 21, 22]}}}
    )

    assert len(m.ports) == 2
    assert m.ports['in2_p'].direction == PortDirection.IN
    assert m.ports['in2_p'].width == 2
    assert m.ports['in2_p'][0].ws_path.raw == 'simpleAdder.in2.0'
    assert m.ports['in2_p'][1].ws_path.raw == 'simpleAdder.in2.1'
    assert m.wires['in2'][0].port_segments[0].raw_path == 'simpleAdder.in2_p.0'
    assert m.wires['in2'][1].port_segments[0].raw_path == 'simpleAdder.in2_p.1'

    assert m.ports['out_p'].direction == PortDirection.OUT
    assert m.ports['out_p'].width == 3
    assert m.ports['out_p'][0].ws_path.raw == 'simpleAdder.out.0'
    assert m.ports['out_p'][1].ws_path.raw == 'simpleAdder.out.1'
    assert m.ports['out_p'][2].ws_path.raw == 'simpleAdder.out.2'
    assert m.wires['out'][0].port_segments[0].raw_path == 'simpleAdder.out_p.0'
    assert m.wires['out'][1].port_segments[0].raw_path == 'simpleAdder.out_p.1'
    assert m.wires['out'][2].port_segments[0].raw_path == 'simpleAdder.out_p.2'


def test_build_port_const(simple_reader: YNR) -> None:
    m = Module(raw_path='simpleAdder')
    simple_reader.net_number_mapping[m.name] = {}
    simple_reader._build_ports(m, {'ports': {'in2_p': {'direction': 'input', 'bits': ['0']}, 'out_p': {'direction': 'output', 'bits': ['1', 'x']}}})

    assert len(m.ports['in2_p']) == 1
    assert m.ports['in2_p'][0].ws_path == WIRE_SEGMENT_0.path
    assert len(m.ports['out_p']) == 2
    assert m.ports['out_p'][0].ws_path == WIRE_SEGMENT_1.path
    assert m.ports['out_p'][1].ws_path == WIRE_SEGMENT_X.path


def test_build_instances(simple_reader: YNR) -> None:
    m = Module(raw_path='simpleAdder')

    # TODO add pytest.raises cases
    m1 = copy.deepcopy(m)
    simple_reader._build_instances(m1, {})
    assert m == m1

    wires = {
        'netnames': {
            '$0\\out[8:0]': {'bits': [29, 30, 31, 32, 33, 34, 35, 36, 37]},
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
                    'B_SIGNED': '00000000000000000000000000000000',
                    'B_WIDTH': '00000000000000000000000000001000',
                    'Y_WIDTH': '00000000000000000000000000001001',
                },
                'attributes': {'src': 'simpleAdder.v:13.15-13.24'},
                'port_directions': {'A': 'input', 'B': 'input', 'Y[3:0]': 'output'},
                'connections': {
                    'A': [4, 5, 6, 7, 8, 9, 10, 11],
                    'B': [12, 13, 14, 15, 16, 17, 18, 19],
                    'Y[3:0]': [29, 30, 31, 32, 33, 34, 35, 36, 37],
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

    with pytest.raises(AttributeError):
        simple_reader.net_number_mapping[m.name] = {}
        simple_reader._build_instances(m, instances)

    simple_reader._build_wires(m, wires)
    simple_reader._build_instances(m, instances)
    assert len(m.instances) == 2
    assert '§add' in m.instances_by_types
    assert '§dff' in m.instances_by_types
    add = m.instances_by_types['§add'][0]
    add.ports.pop('Y')
    adff = m.instances_by_types['§dff'][0]

    assert isinstance(add, Adder)
    assert len(add.parameters) == 5
    assert add.parameters['A_SIGNED'] == 0
    assert add.parameters['A_WIDTH'] == 8
    assert add.parameters['B_SIGNED'] == 0
    assert add.parameters['A_WIDTH'] == 8
    assert add.parameters['Y_WIDTH'] == 9
    assert len(add.ports) == 3
    assert add.input_ports == (add.ports['A'], add.ports['B'])
    assert add.ports['A'].width == 8
    assert add.ports['A'].is_instance_port
    ps = [add.ports['A'][i].raw_ws_path == f'simpleAdder.in1.{i}' for i in add.ports['A'].segments]
    assert all(ps)
    assert add.ports['B'].width == 8
    assert add.ports['B'].is_instance_port
    assert all(add.ports['B'][i].raw_ws_path == f'simpleAdder.in2.{i}' for i in add.ports['B'].segments)
    assert add.ports['Y§3§0§'].width == 9
    assert add.ports['Y§3§0§'].is_instance_port
    assert all(add.ports['Y§3§0§'][i].raw_ws_path == f'simpleAdder.$0\\out[8:0].{i}' for i in add.ports['Y§3§0§'].segments)
    assert simple_reader.port_name_mapping['Y§3§0§'] == [('Y[3:0]', 'simpleAdder.§add§simpleAdder§v§13§2')]
    assert simple_reader.port_name_mapping['Y§3§0§'] == [('Y[3:0]', 'simpleAdder.§add§simpleAdder§v§13§2')]
    for i in range(8):
        assert add.ports['A'][i] in m.wires['in1'][i].port_segments
        assert add.ports['B'][i] in m.wires['in2'][i].port_segments
        assert add.ports['Y§3§0§'][i] in m.wires['$0\\out[8:0]'][i].port_segments

    assert isinstance(adff, DFF)
    assert len(adff.parameters) == 4
    assert adff.parameters['ARST_POLARITY'] == 1
    assert adff.parameters['ARST_VALUE'] == 0
    assert adff.parameters['CLK_POLARITY'] == 1
    assert adff.parameters['WIDTH'] == 9
    assert len(adff.ports) == 5  # 4 Ports from dict + unconnected EN
    assert adff.input_ports == (adff.ports['D'], adff.ports['EN'], adff.ports['CLK'], adff.ports['RST'])
    assert adff.output_port == adff.ports['Q']
    assert adff.ports['D'].width == 9
    assert adff.ports['D'].is_instance_port
    assert all(adff.ports['D'][i].raw_ws_path == f'simpleAdder.$0\\out[8:0].{i}' for i in adff.ports['D'].segments)
    assert adff.ports['CLK'].width == 1
    assert adff.ports['CLK'].is_instance_port
    assert all(adff.ports['CLK'][i].raw_ws_path == f'simpleAdder.clk.{i}' for i in adff.ports['CLK'].segments)
    assert adff.ports['RST'].width == 1
    assert adff.ports['RST'].is_instance_port
    assert all(adff.ports['RST'][i].raw_ws_path == f'simpleAdder.rst.{i}' for i in adff.ports['RST'].segments)
    assert adff.ports['EN'].width == 1
    assert adff.ports['EN'].is_instance_port
    assert all(adff.ports['EN'][i].raw_ws_path == '' for i in adff.ports['EN'].segments)
    assert adff.ports['Q'].width == 9
    assert adff.ports['Q'].is_instance_port
    assert all(adff.ports['Q'][i].raw_ws_path == f'simpleAdder.out.{i}' for i in adff.ports['Q'].segments)


def test_build_instance_port_edge_cases(simple_reader: YNR) -> None:
    simple_reader.net_number_mapping['test'] = {2: WireSegmentPath(raw='test.w.0')}
    m = Module(raw_path='test')
    m.create_wire('w')
    inst = Instance(raw_path='test.instance', instance_type='§and', module=None)
    inst_dict = {'connections': {'A': [2]}, 'port_directions': {}}

    simple_reader._build_instance_ports(m, inst, inst_dict)
    assert len(inst.ports) == 1
    assert inst.ports['A'].direction == PortDirection.UNKNOWN
    assert inst.ports['A'][0].raw_ws_path == 'test.w.0'
    assert m.wires['w'][0].port_segments == [inst.ports['A'][0]]

    inst_dict.pop('port_directions')
    inst = Instance(raw_path='test.instance', instance_type='§and', module=None)
    simple_reader._build_instance_ports(m, inst, inst_dict)
    assert inst.ports == {}


def test_build_instance_port_consts(simple_reader: YNR) -> None:
    simple_reader.net_number_mapping['test'] = {2: WireSegmentPath(raw='')}
    m = Module(raw_path='test')
    inst = Instance(raw_path='test.instance', instance_type='§and', module=None)
    inst_dict = {'connections': {'A': ['0', '1', 'x']}, 'port_directions': {'A': 'input'}}

    simple_reader._build_instance_ports(m, inst, inst_dict)
    assert len(inst.ports) == 1
    assert len(inst.ports['A']) == 3
    assert inst.ports['A'][0].ws_path == WIRE_SEGMENT_0.path
    assert inst.ports['A'][1].ws_path == WIRE_SEGMENT_1.path
    assert inst.ports['A'][2].ws_path == WIRE_SEGMENT_X.path


def test_prepare_dict(simple_reader: YNR) -> None:
    # Currently does nothing, will be expanded later
    simple_reader._prepare_dict('§and', {})

    dff_dict = {'port_directions': {'ARST': 'input'}, 'connections': {'ARST': [2]}}
    simple_reader._prepare_dff_dict('§adffe', dff_dict)

    assert dff_dict == {'port_directions': {'RST': 'input'}, 'connections': {'RST': [2]}}

    dff_dict = {'port_directions': {'ARST': 'input'}, 'connections': {'ARST': [2]}}
    simple_reader._prepare_dff_dict('§dffe', dff_dict)
    assert dff_dict == {'port_directions': {'ARST': 'input'}, 'connections': {'ARST': [2]}}


def test_build_metadata(simple_reader: YNR) -> None:
    m = Module(raw_path='simpleAdder')
    simple_reader._build_metadata(m, {})

    assert len(m.metadata) == 0

    simple_reader._build_metadata(m, {'attributes': {'foo': '42', 'bar': 'baz', 'qux': '000110100100'}})

    assert m.metadata.yosys['foo'] == '42'
    assert m.metadata.yosys['bar'] == 'baz'
    assert m.metadata.yosys['qux'] == 420


def test_build_parameters(simple_reader: YNR) -> None:
    m = Module(raw_path='simpleAdder')
    simple_reader._build_module_parameters(m, {})

    assert m.parameters == {}

    simple_reader._build_module_parameters(m, {'parameters': {'foo': '42', 'bar': 'baz', 'qux': '000110100100'}})

    assert m.parameters['foo'] == '42'
    assert m.parameters['bar'] == 'baz'
    assert m.parameters['qux'] == 420


def test_instance_post_processing(hierarchical_reader: YNR) -> None:
    inst = DFF(raw_path='a.b.c', instance_type='§dff', module=None)
    inst_data = {'parameters': {'ARST_VALUE': '001100'}}  # 12
    hierarchical_reader._instance_post_processing(inst, inst_data)
    assert inst.rst_val_int == 12
    inst_data = {'parameters': {'ARST_VALUE': 42}}
    hierarchical_reader._instance_post_processing(inst, inst_data)
    assert inst.rst_val_int == 42
    inst_data = {'parameters': {'ARST_POLARITY': '1'}}
    hierarchical_reader._instance_post_processing(inst, inst_data)
    assert inst.rst_polarity == Signal.HIGH
    inst_data = {'parameters': {'CLK_POLARITY': '0'}}
    hierarchical_reader._instance_post_processing(inst, inst_data)
    assert inst.clk_polarity == Signal.LOW
    inst_data = {'parameters': {'EN_POLARITY': 0}}
    hierarchical_reader._instance_post_processing(inst, inst_data)
    assert inst.en_polarity == Signal.LOW


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
    CFG.simplify_escaped_identifiers = True
    c = hierarchical_reader.transform_to_circuit('hierarchical')

    assert len(c.modules) == 2
    assert hierarchical_reader.module_definitions == {'§simpleAdder§WIDTH4', 'adderWrapper'}
    assert hierarchical_reader.module_instantiations == {'§simpleAdder§WIDTH4'}
    assert hierarchical_reader.module_definitions_and_instances_match

    assert '§simpleAdder§WIDTH4' in c.modules
    assert 'adderWrapper' in c.modules

    sadder = c['§simpleAdder§WIDTH4']
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


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
