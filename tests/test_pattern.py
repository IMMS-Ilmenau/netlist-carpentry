import os
from pprint import pprint

import networkx as nx
import pytest
import utils

from netlist_carpentry import CFG, EMPTY_GRAPH, EMPTY_PATTERN
from netlist_carpentry.api.read.gen_nl import generate_json_netlist
from netlist_carpentry.api.read.read_utils import read
from netlist_carpentry.api.read.yosys_netlist import YosysNetlistReader as YNR
from netlist_carpentry.core.graph.pattern import Pattern
from netlist_carpentry.core.graph.pattern_generator import PatternGenerator
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.utils.gate_lib import NandGate, XnorGate


@pytest.fixture
def simple_pattern() -> Pattern:
    module = utils.connected_module()
    xor_inst = module.instances['xor_inst']
    g: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    g.add_node(xor_inst.name, ntype=xor_inst.type.name, ntype_info=xor_inst.instance_type, ndata=xor_inst, n_input_inst=True, n_output_inst=True)

    return Pattern(graph=g, ignore_boundary_conditions=True)


def _pattern_graph() -> Pattern:
    module = utils.connected_module()
    g: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    xor_inst = module.instances['xor_inst']
    not_inst = module.instances['not_inst']

    g.add_node(xor_inst.name, ntype=xor_inst.type.name, ntype_info=xor_inst.instance_type, ndata=xor_inst, n_input_inst=True, n_output_inst=False)
    g.add_node(not_inst.name, ntype=not_inst.type.name, ntype_info=not_inst.instance_type, ndata=not_inst, n_input_inst=False, n_output_inst=True)
    g.add_edge(xor_inst.name, not_inst.name, key='Y§A', ename='wire_xor')
    return g


@pytest.fixture
def standard_pattern() -> Pattern:
    g = _pattern_graph()

    return Pattern(graph=g, ignore_boundary_conditions=True)


@pytest.fixture
def standard_pattern_replacement() -> Pattern:
    g = _pattern_graph()

    xnor_inst = XnorGate(raw_path='a.b.c', module=None)

    g_rep: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    g_rep.add_node('new_inst', ntype='INSTANCE', ntype_info='§xnor', ndata=xnor_inst, n_input_inst=True, n_output_inst=True)

    return Pattern(graph=g, replacement_graph=g_rep, ignore_boundary_conditions=True)


@pytest.fixture
def not_found_pattern() -> Pattern:
    module = utils.connected_module()
    g: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    xor_inst = module.instances['xor_inst']
    nand = NandGate(raw_path='a.b.c', module=module)
    g.add_node(xor_inst.name, ntype=xor_inst.type.name, ntype_info=xor_inst.instance_type, ndata=xor_inst, n_input_inst=True, n_output_inst=False)
    g.add_node(nand.name, ntype=nand.type.name, ntype_info=nand.instance_type, ndata=nand, n_input_inst=False, n_output_inst=True)
    g.add_edge(xor_inst.name, nand.name, key='Y§A', ename='wire_xor')

    return Pattern(graph=g, ignore_boundary_conditions=True)


@pytest.fixture
def multi_in_pattern() -> Pattern:
    module = utils.connected_module()
    g: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    and_inst = module.instances['and_inst']
    or_inst = module.instances['or_inst']
    xor_inst = module.instances['xor_inst']

    g.add_node(and_inst.name, ntype=and_inst.type.name, ntype_info=and_inst.instance_type, ndata=and_inst, n_input_inst=True, n_output_inst=False)
    g.add_node(or_inst.name, ntype=or_inst.type.name, ntype_info=or_inst.instance_type, ndata=or_inst, n_input_inst=True, n_output_inst=False)
    g.add_node(xor_inst.name, ntype=xor_inst.type.name, ntype_info=xor_inst.instance_type, ndata=xor_inst, n_input_inst=False, n_output_inst=True)
    g.add_edge(and_inst.name, xor_inst.name, key='Y§A', ename='wire_and')
    g.add_edge(or_inst.name, xor_inst.name, key='Y§B', ename='wire_or')

    return Pattern(graph=g, ignore_port_names=False, ignore_boundary_conditions=True)


@pytest.fixture
def modified_module() -> Module:
    return utils.modified_module()


def test_pattern_init(standard_pattern: Pattern) -> None:
    assert isinstance(EMPTY_PATTERN, Pattern)
    assert EMPTY_PATTERN.graph is EMPTY_GRAPH
    assert len(EMPTY_PATTERN.graph.nodes) == 0
    assert len(EMPTY_PATTERN.graph.edges) == 0
    assert EMPTY_PATTERN.replacement_graph is EMPTY_GRAPH

    assert len(standard_pattern.graph.nodes) == 2
    assert len(standard_pattern.graph.edges) == 1
    assert standard_pattern.replacement_graph is EMPTY_GRAPH


def test_interesting_edges(standard_pattern: Pattern) -> None:
    m = utils.connected_module()
    edges = standard_pattern.interesting_edges(m.graph(), 'xor_inst', set())
    assert len(edges) == 4
    assert ('xor_inst', 'not_inst', 'Y§A') in edges
    assert ('or_inst', 'xor_inst', 'Y§B') in edges
    assert ('and_inst', 'xor_inst', 'Y§A') in edges
    assert ('xor_inst', 'dff_inst', 'Y§D') in edges

    edges = standard_pattern.interesting_edges(m.graph(), 'xor_inst', {'and_inst'})
    assert len(edges) == 4
    assert ('xor_inst', 'not_inst', 'Y§A') in edges
    assert ('or_inst', 'xor_inst', 'Y§B') in edges
    assert ('and_inst', 'xor_inst', 'Y§A') in edges
    assert ('xor_inst', 'dff_inst', 'Y§D') in edges

    edges = standard_pattern.interesting_edges(m.graph(), 'xor_inst', {'and_inst', 'xor_inst'})
    assert len(edges) == 3
    assert ('xor_inst', 'not_inst', 'Y§A') in edges
    assert ('or_inst', 'xor_inst', 'Y§B') in edges
    assert ('xor_inst', 'dff_inst', 'Y§D') in edges

    edges = standard_pattern.interesting_edges(m.graph(), 'xor_inst', {'and_inst', 'xor_inst', 'not_inst', 'or_inst', 'dff_inst'})
    assert len(edges) == 0


def test_find_match_basics(standard_pattern: Pattern, not_found_pattern: Pattern) -> None:
    m = utils.connected_module()

    match = EMPTY_PATTERN.find_matches(m.graph())
    assert list(match.pattern_graph.nodes) == list(EMPTY_PATTERN.graph.nodes)

    match = standard_pattern.find_matches(m.graph())
    assert list(match.pattern_graph.nodes) == list(standard_pattern.graph.nodes)
    assert match.count == 1
    assert nx.isomorphism.is_isomorphic(match.matches.pop(), standard_pattern.graph)

    match = not_found_pattern.find_matches(m.graph())
    assert list(match.pattern_graph.nodes) == list(not_found_pattern.graph.nodes)


def test_find_match_standard(simple_pattern: Pattern, standard_pattern: Pattern, modified_module: Module) -> None:
    match = simple_pattern.find_matches(modified_module.graph())
    assert len(match.matches) == 3
    data_xor1 = list(match.matches[0].nodes.data(data='ntype_info'))
    data_xor2 = list(match.matches[1].nodes.data(data='ntype_info'))
    data_xor3 = list(match.matches[2].nodes.data(data='ntype_info'))

    # Order is not specified!
    assert data_xor1 != data_xor2
    assert data_xor1 != data_xor3
    assert data_xor2 != data_xor3

    assert data_xor1 == [('xor_inst', '§xor')] or data_xor1 == [('xor2_inst', '§xor')] or data_xor1 == [('xor3_inst', '§xor')]
    assert data_xor2 == [('xor_inst', '§xor')] or data_xor2 == [('xor2_inst', '§xor')] or data_xor2 == [('xor3_inst', '§xor')]
    assert data_xor3 == [('xor_inst', '§xor')] or data_xor3 == [('xor2_inst', '§xor')] or data_xor3 == [('xor3_inst', '§xor')]

    match = standard_pattern.find_matches(modified_module.graph())
    assert len(match.matches) == 3
    data1 = list(match.matches[0].nodes.data(data='ntype_info'))
    data2 = list(match.matches[1].nodes.data(data='ntype_info'))
    data3 = list(match.matches[2].nodes.data(data='ntype_info'))
    # Order is not specified!
    assert data1 != data2
    assert data1 != data3
    assert data2 != data3

    assert (
        data1 == [('xor_inst', '§xor'), ('not_inst', '§not')]
        or data1 == [('xor2_inst', '§xor'), ('not2_inst', '§not')]
        or data1 == [('xor3_inst', '§xor'), ('not3_inst', '§not')]
    )
    assert (
        data2 == [('xor_inst', '§xor'), ('not_inst', '§not')]
        or data2 == [('xor2_inst', '§xor'), ('not2_inst', '§not')]
        or data2 == [('xor3_inst', '§xor'), ('not3_inst', '§not')]
    )
    assert (
        data3 == [('xor_inst', '§xor'), ('not_inst', '§not')]
        or data3 == [('xor2_inst', '§xor'), ('not2_inst', '§not')]
        or data3 == [('xor3_inst', '§xor'), ('not3_inst', '§not')]
    )


def test_count_matches_basics(standard_pattern: Pattern, not_found_pattern: Pattern) -> None:
    m = utils.connected_module()

    matches = EMPTY_PATTERN.count_matches(m.graph())
    assert matches == 0

    matches = standard_pattern.count_matches(m.graph())
    assert matches == 1

    matches = not_found_pattern.count_matches(m.graph())
    assert matches == 0


def test_count_matches_standard(simple_pattern: Pattern, standard_pattern: Pattern, modified_module: Module) -> None:
    matches = simple_pattern.count_matches(modified_module.graph())
    assert matches == 3

    matches = standard_pattern.count_matches(modified_module.graph())
    assert matches == 3


def test_complex_count_matches(multi_in_pattern: Pattern) -> None:
    m = utils.connected_module()

    matches = multi_in_pattern.count_matches(m.graph())
    assert matches == 1

    # Change port connection -> pattern should no longer match
    or_inst = m.get_instance('or_inst')
    xor_inst = m.get_instance('xor_inst')
    multi_in_pattern.graph.remove_edge(or_inst.name, xor_inst.name, key='Y§B')
    multi_in_pattern.graph.add_edge(or_inst.name, xor_inst.name, key='Y§A')
    matches = multi_in_pattern.count_matches(m.graph())
    assert matches == 0


def test_replacement_locked(standard_pattern_replacement: Pattern) -> None:
    m = utils.locked_module()

    standard_pattern_replacement.mapping = {}
    did_replace = standard_pattern_replacement.replace(m)
    assert did_replace == 0


def test_replacement(standard_pattern_replacement: Pattern) -> None:
    m = utils.modified_module()

    assert 'not_inst' in m.instances
    assert 'xor_inst' in m.instances
    assert 'not2_inst' in m.instances
    assert 'xor2_inst' in m.instances
    assert 'not3_inst' in m.instances
    assert 'xor3_inst' in m.instances
    assert 'new_inst' not in m.instances

    mapping = {
        ('new_inst', 'A', 0): ('xor_inst', 'A', 0),
        ('new_inst', 'B', 0): ('xor_inst', 'B', 0),
        ('new_inst', 'Y', 0): ('not_inst', 'Y', 0),
    }
    standard_pattern_replacement.mapping = mapping
    did_replace = standard_pattern_replacement.replace(m)

    assert did_replace == 3

    assert 'not_inst' not in m.instances
    assert 'xor_inst' not in m.instances
    assert 'not2_inst' not in m.instances
    assert 'xor2_inst' not in m.instances
    # Unconnected, but replaced nonetheless
    assert 'not3_inst' not in m.instances
    assert 'xor3_inst' not in m.instances
    # New instance replacing old instances
    assert 'new_inst__replaced0' in m.instances
    assert 'new_inst__replaced1' in m.instances
    assert 'new_inst__replaced2' in m.instances

    rep0 = m.instances['new_inst__replaced0']
    rep1 = m.instances['new_inst__replaced1']
    rep2 = m.instances['new_inst__replaced2']
    assert rep0.instance_type == '§xnor'
    assert rep1.instance_type == '§xnor'
    assert rep2.instance_type == '§xnor'

    xnor1_1 = m.get_succeeding_instances(m.instances['and_inst'].name)['Y']
    xnor1_2 = m.get_succeeding_instances(m.instances['or_inst'].name)['Y']
    assert xnor1_1 == xnor1_2
    assert len(xnor1_1[0]) == 1
    assert xnor1_1[0][0].instance_type == '§xnor'
    assert xnor1_1[0][0].name == 'new_inst__replaced0' or xnor1_1[0][0].name == 'new_inst__replaced1' or xnor1_1[0][0].name == 'new_inst__replaced2'

    succ_insts = m.get_succeeding_instances(xnor1_1[0][0].name)['Y'][0]
    assert len(succ_insts) == 2
    xnor2 = succ_insts[0] if isinstance(succ_insts[0], Instance) else succ_insts[1]
    port = succ_insts[0] if isinstance(succ_insts[0], Port) else succ_insts[1]
    assert xnor2.instance_type == '§xnor'
    assert xnor2.name == 'new_inst__replaced0' or xnor2.name == 'new_inst__replaced1'
    assert xnor1_1[0][0].name != xnor2.name
    assert port.name == 'out'


def test_replacement_partly_locked(standard_pattern_replacement: Pattern) -> None:
    m = utils.modified_module()

    m.instances['not_inst'].change_mutability(is_now_locked=True)
    mapping = {
        ('new_inst', 'A', 0): ('xor_inst', 'A', 0),
        ('new_inst', 'B', 0): ('xor_inst', 'B', 0),
        ('new_inst', 'Y', 0): ('not_inst', 'Y', 0),
    }
    standard_pattern_replacement.mapping = mapping
    did_replace = standard_pattern_replacement.replace(m, replace_all_parallel=True)

    assert did_replace == 2

    # Not changed because of immutability
    assert 'not_inst' in m.instances
    assert 'xor_inst' in m.instances
    assert 'not2_inst' not in m.instances
    assert 'xor2_inst' not in m.instances
    # Unconnected, but replaced nonetheless
    assert 'not3_inst' not in m.instances
    assert 'xor3_inst' not in m.instances
    # New instance replacing old instances, but only in one occasion
    assert 'new_inst__replaced0' in m.instances
    assert 'new_inst__replaced1' in m.instances

    rep0 = m.instances['new_inst__replaced0']
    assert rep0.instance_type == '§xnor'
    rep1 = m.instances['new_inst__replaced1']
    assert rep1.instance_type == '§xnor'


def test_replacement_1_iteration(standard_pattern_replacement: Pattern) -> None:
    m = utils.modified_module()

    mapping = {
        ('new_inst', 'A', 0): ('xor_inst', 'A', 0),
        ('new_inst', 'B', 0): ('xor_inst', 'B', 0),
        ('new_inst', 'Y', 0): ('not_inst', 'Y', 0),
    }
    standard_pattern_replacement.mapping = mapping
    replacements = standard_pattern_replacement.replace(m, iterations=1)
    assert replacements == 1


def test_build_pattern_circuit() -> None:
    find_pattern_file = 'tests/files/or_pattern_find.v'
    replace_pattern_file = 'tests/files/or_pattern_replace.v'
    find_circuit = read(find_pattern_file)
    replace_circuit = read(replace_pattern_file)

    p = PatternGenerator.build_from_circuit(find_circuit, remove_ports=False)
    assert len(p.graph.nodes) == 4 + 3 + 1  # 4 input ports, 3 instances, 1 output port
    assert len(p.graph.edges) == 7  # Total of 7 edges in the graph
    assert len(p.replacement_graph.nodes) == 0  # Unspecified graph
    assert len(p.replacement_graph.edges) == 0  # Unspecified graph

    Pattern._remove_ports_from_pattern_graphs(p.graph)
    assert len(p.graph.nodes) == 3  # 3 instances
    assert len(p.graph.edges) == 2  # Total of 2 edges now left in the graph

    p = PatternGenerator.build_from_circuit(find_circuit, replace_circuit, remove_ports=True)
    assert len(p.graph.nodes) == 3  # 3 instances, removed ports directly
    assert len(p.graph.edges) == 2  # Total of 2 edges in the graph, since all edges related to module input/output have also been removed
    assert len(p.replacement_graph.nodes) == 3  # 3 instances, removed ports directly
    assert len(p.replacement_graph.edges) == 2  # Total of 2 edges in the graph, since all edges related to module input/output have also been removed


def test_build_pattern_verilog() -> None:
    find_pattern_file = 'tests/files/or_pattern_find.v'
    replace_pattern_file = 'tests/files/or_pattern_replace.v'

    p = PatternGenerator.build_from_verilog(find_pattern_file, remove_ports=False)
    assert len(p.graph.nodes) == 4 + 3 + 1  # 4 input ports, 3 instances, 1 output port
    assert len(p.graph.edges) == 7  # Total of 7 edges in the graph
    assert len(p.replacement_graph.nodes) == 0  # Unspecified graph
    assert len(p.replacement_graph.edges) == 0  # Unspecified graph

    Pattern._remove_ports_from_pattern_graphs(p.graph)
    assert len(p.graph.nodes) == 3  # 3 instances
    assert len(p.graph.edges) == 2  # Total of 2 edges now left in the graph

    p = PatternGenerator.build_from_verilog(find_pattern_file, replace_pattern_file, remove_ports=True)
    assert len(p.graph.nodes) == 3  # 3 instances, removed ports directly
    assert len(p.graph.edges) == 2  # Total of 2 edges in the graph, since all edges related to module input/output have also been removed
    assert len(p.replacement_graph.nodes) == 3  # 3 instances, removed ports directly
    assert len(p.replacement_graph.edges) == 2  # Total of 2 edges in the graph, since all edges related to module input/output have also been removed


def test_build_pattern_yosys() -> None:
    generate_json_netlist('tests/files/or_pattern_find.v', 'or_pattern_find.json')
    generate_json_netlist('tests/files/or_pattern_replace.v', 'or_pattern_replace.json')
    find_pattern_file = 'tests/files/or_pattern_find.json'
    replace_pattern_file = 'tests/files/or_pattern_replace.json'

    p = PatternGenerator.build_from_yosys_netlists(find_pattern_file, remove_ports=False)
    assert len(p.graph.nodes) == 4 + 3 + 1  # 4 input ports, 3 instances, 1 output port
    assert len(p.graph.edges) == 7  # Total of 7 edges in the graph
    assert len(p.replacement_graph.nodes) == 0  # Unspecified graph
    assert len(p.replacement_graph.edges) == 0  # Unspecified graph

    Pattern._remove_ports_from_pattern_graphs(p.graph)
    assert len(p.graph.nodes) == 3  # 3 instances
    assert len(p.graph.edges) == 2  # Total of 2 edges now left in the graph

    p = PatternGenerator.build_from_yosys_netlists(find_pattern_file, replace_pattern_file, remove_ports=True)
    assert len(p.graph.nodes) == 3  # 3 instances, removed ports directly
    assert len(p.graph.edges) == 2  # Total of 2 edges in the graph, since all edges related to module input/output have also been removed
    assert len(p.replacement_graph.nodes) == 3  # 3 instances, removed ports directly
    assert len(p.replacement_graph.edges) == 2  # Total of 2 edges in the graph, since all edges related to module input/output have also been removed


def test_graph_from_file_fail() -> None:
    generate_json_netlist('tests/files/dec.v', 'dec.json')
    with pytest.raises(ValueError):
        # Contains multiple modules
        PatternGenerator._module_from_json('tests/files/dec.json', remove_ports=True)


def test_add_node_metadata() -> None:
    g: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    g.add_node('A', ntype='PORT', ntype_info='input')
    g.add_node('N', ntype='INSTANCE')
    g.add_node('Y', ntype='PORT', ntype_info='output')
    g.add_edge('A', 'N')
    g.add_edge('N', 'Y')
    Pattern._add_node_metadata(g)
    assert g.nodes['N']['n_input_inst']
    assert g.nodes['N']['n_output_inst']

    g: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    g.add_node('A', ntype='PORT', ntype_info='input')
    g.add_node('N', ntype='INSTANCE')
    g.add_node('M', ntype='INSTANCE')
    g.add_node('Y', ntype='PORT', ntype_info='output')
    g.add_edge('A', 'N')
    g.add_edge('N', 'M')
    g.add_edge('M', 'Y')
    Pattern._add_node_metadata(g)
    assert g.nodes['N']['n_input_inst']
    assert not g.nodes['N']['n_output_inst']
    assert g.nodes['M']['n_output_inst']
    assert not g.nodes['M']['n_input_inst']


def test_get_mapping() -> None:
    CFG.simplify_escaped_identifiers = True
    find_pattern_file = 'tests/files/or_pattern_find.json'
    replace_pattern_file = 'tests/files/or_pattern_replace.json'

    target_mapping = {
        ('§or§or_pattern_replace§v§30§1', 'A', -1): ('§or§or_pattern_find§v§34§1', 'A', -1),
        ('§or§or_pattern_replace§v§30§1', 'B', -1): ('§or§or_pattern_find§v§34§1', 'B', -1),
        ('§or§or_pattern_replace§v§31§2', 'A', -1): ('§or§or_pattern_find§v§36§2', 'B', -1),
        ('§or§or_pattern_replace§v§31§2', 'B', -1): ('§or§or_pattern_find§v§38§3', 'B', -1),
        ('§or§or_pattern_replace§v§32§3', 'Y', -1): ('§or§or_pattern_find§v§38§3', 'Y', -1),
    }
    find_module = YNR(find_pattern_file).transform_to_circuit().first
    replace_module = YNR(replace_pattern_file).transform_to_circuit().first
    found_mapping = Pattern.get_mapping(find_module, replace_module)
    pprint(found_mapping)
    for map_k, map_v in target_mapping.items():
        assert map_k in found_mapping
        assert found_mapping[map_k] == map_v


def test_get_mapping_not_matching() -> None:
    find_pattern_file = 'tests/files/or_pattern_find.json'
    not_matching_file = 'tests/files/simpleAdder.json'

    find_module = YNR(find_pattern_file).transform_to_circuit().first
    replace_module = YNR(not_matching_file).transform_to_circuit().first
    with pytest.raises(ValueError):
        Pattern.get_mapping(find_module, replace_module)


def test_build_pattern_edge_cases() -> None:
    CFG.simplify_escaped_identifiers = True
    multi_module_path = 'tests/files/adderWrapper.json'
    with pytest.raises(ValueError):
        PatternGenerator.build_from_yosys_netlists(multi_module_path)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
