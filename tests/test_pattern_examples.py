import os
from pathlib import Path

import pytest
from utils import save_results

from netlist_carpentry import CFG, LOG, read
from netlist_carpentry.api.read.gen_nl import generate_json_netlist
from netlist_carpentry.api.write.py2v import P2VTransformer as P2V
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.graph.constraint import CASCADING_OR_CONSTRAINT
from netlist_carpentry.core.graph.pattern import Pattern
from netlist_carpentry.core.graph.pattern_generator import PatternGenerator
from netlist_carpentry.scripts.cascading_or_replacement import cascading_or_replacement
from netlist_carpentry.utils.gate_lib import OrGate
from netlist_carpentry.utils.log import Log, initialize_logging

file_path = os.path.realpath(__file__)
file_dir_path = os.path.dirname(file_path)
LOG_DIRECTORY = file_dir_path + '/logs/'
LOG_NAME = 'log_pattern_examples_write.log'
LOG_PATH = LOG_DIRECTORY + LOG_NAME


@pytest.fixture
def log_setup() -> Log:
    CFG.log_level = 1
    initialize_logging(LOG_DIRECTORY, custom_file_name=LOG_NAME)
    return LOG


@pytest.fixture
def dec_mux_circuit() -> Circuit:
    CFG.simplify_escaped_identifiers = True
    return read('tests/files/decentral_mux.v')


@pytest.fixture
def dec_mux_pattern() -> Pattern:
    CFG.simplify_escaped_identifiers = True
    find_pattern_file = 'tests/files/or_pattern_find.json'
    replace_pattern_file = 'tests/files/or_pattern_replace.json'
    p = PatternGenerator.build_from_yosys_netlists(find_pattern_file, replace_pattern_file, constraints=[CASCADING_OR_CONSTRAINT])
    p._ignore_boundary_conditions = True  # TODO should not be an issue, check again!
    return p


def test_decentral_mux_pattern_matching(dec_mux_circuit: Circuit, dec_mux_pattern: Pattern) -> None:
    mux_module = dec_mux_circuit.first
    mux_module_graph = mux_module.graph()
    m = dec_mux_pattern.find_matches(mux_module_graph)
    assert len(mux_module.instances_by_types['§or']) == 15
    assert m.count == 13


def test_decentral_mux_pattern_replacement(dec_mux_circuit: Circuit, dec_mux_pattern: Pattern, log_setup: Log) -> None:
    mux_module = dec_mux_circuit.first
    mapping = {
        ('§or§or_pattern_replace§v§30§1', 'A', -1): ('§or§or_pattern_find§v§34§1', 'A', -1),
        ('§or§or_pattern_replace§v§30§1', 'B', -1): ('§or§or_pattern_find§v§34§1', 'B', -1),
        ('§or§or_pattern_replace§v§31§2', 'A', -1): ('§or§or_pattern_find§v§36§2', 'B', -1),
        ('§or§or_pattern_replace§v§31§2', 'B', -1): ('§or§or_pattern_find§v§38§3', 'B', -1),
        ('§or§or_pattern_replace§v§32§3', 'Y', -1): ('§or§or_pattern_find§v§38§3', 'Y', -1),
    }
    nr_inst_before = len(mux_module.instances)
    dec_mux_pattern.mapping = mapping
    replacement_cnt = dec_mux_pattern.replace(mux_module)
    save_results(P2V().module2v(mux_module), 'v')
    nr_inst_after = len(mux_module.instances)
    assert nr_inst_before == nr_inst_after
    assert replacement_cnt
    for or_g in mux_module.instances_by_types['§or']:
        assert isinstance(or_g, OrGate)
        assert or_g.ports['A'][0].raw_ws_path != ''
        assert or_g.ports['B'][0].raw_ws_path != ''
        assert or_g.ports['Y'][0].raw_ws_path != ''


def test_decentral_mux_pattern_replacement_fnc() -> None:
    generate_json_netlist('tests/files/decentral_mux.v', 'decentral_mux.json')
    cascading_or_replacement(Path('tests/files/decentral_mux.json'), 'tests/files/gen/decentral_mux_fnc_replaced.v')
    c_before = read('tests/files/decentral_mux.v')
    c_after = read('./tests/files/gen/decentral_mux_fnc_replaced.v')
    m_before = c_before.first
    m_after = c_after.first

    nr_inst_before = len(m_before.instances)
    nr_inst_after = len(m_after.instances)
    assert nr_inst_before == nr_inst_after
    for or_g in m_after.instances_by_types['§or']:
        assert isinstance(or_g, OrGate)
        assert or_g.ports['A'][0].raw_ws_path != ''
        assert or_g.ports['B'][0].raw_ws_path != ''
        assert or_g.ports['Y'][0].raw_ws_path != ''


def test_simple_or_structure_replacement(dec_mux_pattern: Pattern) -> None:
    simple_or = read('tests/files/simple_or_structure.v')
    or_module = simple_or.first
    mapping = {
        ('§or§or_pattern_replace§v§30§1', 'A', -1): ('§or§or_pattern_find§v§34§1', 'A', -1),
        ('§or§or_pattern_replace§v§30§1', 'B', -1): ('§or§or_pattern_find§v§34§1', 'B', -1),
        ('§or§or_pattern_replace§v§31§2', 'A', -1): ('§or§or_pattern_find§v§36§2', 'B', -1),
        ('§or§or_pattern_replace§v§31§2', 'B', -1): ('§or§or_pattern_find§v§38§3', 'B', -1),
        ('§or§or_pattern_replace§v§32§3', 'Y', -1): ('§or§or_pattern_find§v§38§3', 'Y', -1),
    }
    nr_inst_before = len(or_module.instances)
    dec_mux_pattern.mapping = mapping
    replacement_cnt = dec_mux_pattern.replace(or_module)
    save_results(P2V().module2v(or_module), 'v')
    nr_inst_after = len(or_module.instances)
    assert nr_inst_before == nr_inst_after
    assert replacement_cnt
    for or_g in or_module.instances_by_types['§or']:
        assert isinstance(or_g, OrGate)
        assert or_g.ports['A'][0].raw_ws_path != ''
        assert or_g.ports['B'][0].raw_ws_path != ''
        assert or_g.ports['Y'][0].raw_ws_path != ''


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
