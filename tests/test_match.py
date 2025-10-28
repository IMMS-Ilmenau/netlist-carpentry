import os

import pytest
import utils
from networkx import MultiDiGraph

from netlist_carpentry.core.graph.match import Match
from netlist_carpentry.core.graph.pattern import Pattern
from netlist_carpentry.core.netlist_elements.module import Module


@pytest.fixture
def empty_match() -> Match:
    g = MultiDiGraph()
    return Match(g, set())


def standard_pattern() -> Pattern:
    module = utils.connected_module()
    g = MultiDiGraph()
    xor_inst = module.get_instance('xor_inst')
    not_inst = module.get_instance('not_inst')

    g.add_node(xor_inst.name, ntype=xor_inst.type.name, ntype_info=xor_inst.instance_type, ndata=xor_inst)
    g.add_node(not_inst.name, ntype=not_inst.type.name, ntype_info=not_inst.instance_type, ndata=not_inst)
    g.add_edge(xor_inst.name, not_inst.name, key='Y§A', ename='wire_xor')

    return Pattern(graph=g, ignore_boundary_conditions=True)


@pytest.fixture()
def standard_match() -> Match:
    return standard_pattern().find_matches(utils.modified_module().graph())


@pytest.fixture()
def mod_module() -> Module:
    return utils.modified_module()


def test_match_init(empty_match: Match) -> None:
    assert len(empty_match.pattern_graph.nodes) == 0
    assert empty_match.matches == {0} - {0}  # Funny eyes <=> empty set
    assert empty_match.count == 0


def test_match_get_pairs(standard_match: Match) -> None:
    target_pairing = {'xor_inst': {0: 'xor_inst', 1: 'xor2_inst', 2: 'xor3_inst'}, 'not_inst': {0: 'not_inst', 1: 'not2_inst', 2: 'not3_inst'}}
    found_pairing = standard_match.pairings
    assert len(found_pairing) == 2
    assert len(found_pairing['xor_inst']) == 3
    assert len(found_pairing['not_inst']) == 3
    assert 'xor_inst' in found_pairing['xor_inst'].values()
    assert 'xor2_inst' in found_pairing['xor_inst'].values()
    assert 'not_inst' in found_pairing['not_inst'].values()
    assert 'not2_inst' in found_pairing['not_inst'].values()
    assert set(target_pairing['xor_inst'].values()) == set(found_pairing['xor_inst'].values())
    assert set(target_pairing['not_inst'].values()) == set(found_pairing['not_inst'].values())
    assert (
        (found_pairing['xor_inst'][0] == 'xor_inst' and found_pairing['not_inst'][0] == 'not_inst')
        or (found_pairing['xor_inst'][1] == 'xor_inst' and found_pairing['not_inst'][1] == 'not_inst')
        or (found_pairing['xor_inst'][2] == 'xor_inst' and found_pairing['not_inst'][2] == 'not_inst')
    )
    assert (
        (found_pairing['xor_inst'][0] == 'xor2_inst' and found_pairing['not_inst'][0] == 'not2_inst')
        or (found_pairing['xor_inst'][1] == 'xor2_inst' and found_pairing['not_inst'][1] == 'not2_inst')
        or (found_pairing['xor_inst'][2] == 'xor2_inst' and found_pairing['not_inst'][2] == 'not2_inst')
    )
    assert (
        (found_pairing['xor_inst'][0] == 'xor3_inst' and found_pairing['not_inst'][0] == 'not3_inst')
        or (found_pairing['xor_inst'][1] == 'xor3_inst' and found_pairing['not_inst'][1] == 'not3_inst')
        or (found_pairing['xor_inst'][2] == 'xor3_inst' and found_pairing['not_inst'][2] == 'not3_inst')
    )


def test_get_interfaces(standard_match: Match, mod_module: Module) -> None:
    # Dictionary of each found subgraph and its instances, where all ports are listed that are connected.
    # The only unconnected ports are the input port B of the xor instance in the second found subgraph, and the output port of the second not instance.
    # Both ports are thus not included in the interface structure to show the lacking connection data.
    # The tuple contains the connected instances with their ports of the circuit instance.
    # The output of the 'not_inst' is connected directly to the module output and thus there is no instance, indicated by 'None'.
    # The dict with key 2 is the occurrence in the graph which is unconnected from the environment.
    # Thus only the connections between the pattern instances are considered.
    target_if = {
        0: {
            ('xor_inst', 'A', 0): {('and_inst', 'Y', 0)},
            ('xor_inst', 'B', 0): {('or_inst', 'Y', 0)},
            ('xor_inst', 'Y', 0): {('dff_inst', 'D', 0), ('not_inst', 'A', 0)},
            ('not_inst', 'A', 0): {('xor_inst', 'Y', 0)},
            ('not_inst', 'Y', 0): {(None, 'out', 0), ('xor2_inst', 'A', 0)},
        },
        1: {
            ('xor2_inst', 'A', 0): {('not_inst', 'Y', 0)},
            # xor2_inst , 'B'
            ('xor2_inst', 'Y', 0): {('not2_inst', 'A', 0)},
            ('not2_inst', 'A', 0): {('xor2_inst', 'Y', 0)},
            # not2_inst , 'Y'
        },
        2: {('not3_inst', 'A', 0): {('xor3_inst', 'Y', 0)}, ('xor3_inst', 'Y', 0): {('not3_inst', 'A', 0)}},
    }
    found_if = standard_match.get_interfaces(mod_module.graph())

    assert target_if[0] == found_if[0] or target_if[1] == found_if[0] or target_if[2] == found_if[0]
    assert target_if[0] == found_if[1] or target_if[1] == found_if[1] or target_if[2] == found_if[1]
    assert target_if[0] == found_if[2] or target_if[1] == found_if[2] or target_if[2] == found_if[2]


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
