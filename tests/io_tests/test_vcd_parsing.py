import os
from typing import List

import pytest
from pywellen import Waveform

from netlist_carpentry import CFG, Circuit, read
from netlist_carpentry.core.exceptions import VcdLoadingError
from netlist_carpentry.io.vcd.parsing import (
    _refine_partition,
    apply_vcd_data,
    equal_toggles,
    filter_signals,
    filter_signals_per_scope,
    find_matching_signals,
    get_hierarchy_dict,
    get_scope,
    map_names_to_circuit,
    partition_all_vcd_signals,
)
from netlist_carpentry.io.vcd.wrapper import VCDWaveform
from netlist_carpentry.utils.gate_lib import AndGate
from tests.test_verilog import _setup_run_circuit


def _gen_vcd(vpaths: List[str], tbname: str) -> None:
    c = read(vpaths)
    _setup_run_circuit(tbname, c)


@pytest.fixture()
def adder_vcd() -> VCDWaveform:
    _gen_vcd(['tests/files/simpleAdder.v'], 'adder_basics')
    return VCDWaveform(Waveform('tests/files/sim/adder_basics/tb_adder_basics.vcd'))


@pytest.fixture()
def adder_toggle_together() -> VCDWaveform:
    _gen_vcd(['tests/files/simpleAdder.v'], 'adder_toggle_together')
    return VCDWaveform(Waveform('tests/files/sim/adder_toggle_together/tb_adder_basics.vcd'))


@pytest.fixture()
def unique_signals() -> VCDWaveform:
    _gen_vcd(['tests/files/simpleAdder.v'], 'unique_signals')
    return VCDWaveform(Waveform('tests/files/sim/unique_signals/tb_unique_signals.vcd'))


@pytest.fixture()
def no_signals() -> VCDWaveform:
    _gen_vcd(['tests/files/simpleAdder.v'], 'no_signals')
    return VCDWaveform(Waveform('tests/files/sim/no_signals/tb_no_signals.vcd'))


@pytest.fixture()
def wrapper_vcd() -> VCDWaveform:
    _gen_vcd(['tests/files/adderWrapper.v', 'tests/files/simpleAdder.v'], 'adderWrapper')
    return VCDWaveform(Waveform('tests/files/sim/adderWrapper/tb_adderWrapper.vcd'))


@pytest.fixture()
def adder() -> Circuit:
    return read('tests/files/simpleAdder.v')


@pytest.fixture()
def adder_wrapper() -> Circuit:
    return read(['tests/files/adderWrapper.v', 'tests/files/simpleAdder.v'], top='adderWrapper')


def test_get_hierarchy_dict(adder_vcd: VCDWaveform, wrapper_vcd: VCDWaveform) -> None:
    hdict = get_hierarchy_dict(adder_vcd)
    assert hdict == {'tb_adder_basics': {'adder': {}}}

    hdict = get_hierarchy_dict(wrapper_vcd)
    assert hdict == {'tb_adderWrapper': {'I_adderWrapper': {'adder': {}}}}


def test_get_scope(adder_vcd: VCDWaveform, wrapper_vcd: VCDWaveform, adder: Circuit, adder_wrapper: Circuit) -> None:
    scope = get_scope(adder_vcd, 'adder')
    assert scope.full_name == 'tb_adder_basics.adder'

    scope = get_scope(wrapper_vcd, 'I_adderWrapper')
    assert scope.full_name == 'tb_adderWrapper.I_adderWrapper'

    with pytest.raises(VcdLoadingError):
        get_scope(adder_vcd, 'I_adderWrapper')
    with pytest.raises(VcdLoadingError):
        get_scope(adder_vcd, 'non_existing_name')


def test_map_names_to_circuit(wrapper_vcd: VCDWaveform, adder_wrapper: Circuit) -> None:
    name_map = map_names_to_circuit(adder_wrapper, wrapper_vcd, 'I_adderWrapper')
    assert name_map == {
        'tb_adderWrapper.I_adderWrapper': adder_wrapper.top,
        'tb_adderWrapper.I_adderWrapper.adder': adder_wrapper['§simpleAdder§WIDTH§4'],
    }


def test_map_names_to_circuit_edge_cases(wrapper_vcd: VCDWaveform) -> None:
    c = Circuit(name='c')
    m = c.create_module(name='adderWrapper')
    c.set_top('adderWrapper')
    with pytest.raises(VcdLoadingError):  # Cannot map VCD scope object adder to an instance of module adderWrapper!
        map_names_to_circuit(c, wrapper_vcd, 'I_adderWrapper')
    m.create_instance(AndGate, 'adder')
    with pytest.raises(VcdLoadingError):  # No module instance found for instance tb_adderWrapper.I_adderWrapper.adder!
        map_names_to_circuit(c, wrapper_vcd, 'I_adderWrapper')


def test_apply_vcd_data(adder_wrapper: Circuit, wrapper_vcd: VCDWaveform) -> None:
    apply_vcd_data(adder_wrapper, wrapper_vcd, 'I_adderWrapper')
    m = adder_wrapper.first
    for w in m.wires.values():
        assert w.metadata.has_category('vcd')
        for name, activity in w.metadata.vcd.items():
            assert isinstance(name, str)
            assert w.name.replace(CFG.id_internal, CFG.id_external) in name
            assert isinstance(activity, list)
            for tup in activity:
                assert isinstance(tup, tuple)
                assert len(tup) == 2


def test_equal_toggles(wrapper_vcd: VCDWaveform) -> None:
    sigs = equal_toggles(wrapper_vcd)
    assert len(sigs) == 5  # 4 as below + clk
    assert (0,) in sigs
    assert (0, 1350) in sigs
    assert (0, 310, 610, 1050) in sigs

    inner_scope = wrapper_vcd.top_scopes[0].scopes[0]
    sigs = filter_signals(wrapper_vcd, scope=inner_scope)
    assert len(sigs) == 5
    assert len(sigs[(0,)]) == 1
    assert len(sigs[(0, 1350)]) == 2
    assert len(sigs[(0, 310, 610, 1050)]) == 1

    first_var = next(iter(wrapper_vcd.all_vars.values()))
    sigs = filter_signals(wrapper_vcd, scope=inner_scope, vcd_vars={first_var, 'tb_adderWrapper.in2'})
    assert len(sigs) == 2
    assert sigs[(0, 1350)][0].full_name == 'tb_adderWrapper.in2'


def test_filter_signals(wrapper_vcd: VCDWaveform) -> None:
    sigs = filter_signals(wrapper_vcd, min_occurences=4)
    assert len(sigs) == 2  # two of the 4 below, and not the clk
    assert (0,) not in sigs
    assert (0, 1350) in sigs
    assert (0, 310, 610, 1050) not in sigs

    sigs = filter_signals(wrapper_vcd, min_changes=1)
    assert len(sigs) == 4  # 3 of the 4 below + clk
    assert (0,) not in sigs
    assert (0, 1350) in sigs
    assert (0, 310, 610, 1050) in sigs

    inner_scope = wrapper_vcd.top_scopes[0].scopes[0]
    sigs = filter_signals(wrapper_vcd, scope=inner_scope, min_occurences=2, min_changes=1)
    assert len(sigs) == 2
    assert (0,) not in sigs
    assert len(sigs[(0, 1350)]) == 2
    assert (0, 310, 610, 1050) not in sigs


def test_filter_signals_unique(unique_signals: VCDWaveform) -> None:
    sigs = filter_signals(unique_signals, min_occurences=1)
    assert len(sigs) == 5

    sigs = filter_signals(unique_signals, min_occurences=2)
    assert len(sigs) == 0


def test_filter_signals_per_scope(wrapper_vcd: VCDWaveform) -> None:
    sig_dict = {}
    filter_signals_per_scope(wrapper_vcd, None, sig_dict)
    assert len(sig_dict) == 3
    assert 'tb_adderWrapper' in sig_dict
    assert 'tb_adderWrapper.I_adderWrapper' in sig_dict
    assert 'tb_adderWrapper.I_adderWrapper.adder' in sig_dict

    sig_dict = {}
    filter_signals_per_scope(wrapper_vcd, wrapper_vcd.top_scopes[0].scopes[0], sig_dict)
    assert len(sig_dict) == 2
    assert 'tb_adderWrapper.I_adderWrapper' in sig_dict
    assert 'tb_adderWrapper.I_adderWrapper.adder' in sig_dict


def test_find_matching_signals(adder_toggle_together: VCDWaveform, adder_vcd: VCDWaveform) -> None:
    wf_paths = ['tests/files/sim/adder_toggle_together/tb_adder_basics.vcd', 'tests/files/sim/adder_basics/tb_adder_basics.vcd']
    sigs = find_matching_signals(wf_paths)
    assert len(sigs) == 5
    assert ['tb_adder_basics.out', 'tb_adder_basics.adder.out'] in sigs
    assert ['tb_adder_basics.clk', 'tb_adder_basics.adder.clk'] in sigs
    assert ['tb_adder_basics.in1', 'tb_adder_basics.adder.in1'] in sigs
    assert ['tb_adder_basics.in2', 'tb_adder_basics.adder.in2'] in sigs
    assert ['tb_adder_basics.rst_n', 'tb_adder_basics.adder.rst'] in sigs

    wf_paths = ['tests/files/sim/adder_basics/tb_adder_basics.vcd', 'tests/files/sim/adder_toggle_together/tb_adder_basics.vcd']
    sigs = find_matching_signals(wf_paths)
    assert len(sigs) == 5
    assert ['tb_adder_basics.out', 'tb_adder_basics.adder.out'] in sigs
    assert ['tb_adder_basics.clk', 'tb_adder_basics.adder.clk'] in sigs
    assert ['tb_adder_basics.in1', 'tb_adder_basics.adder.in1'] in sigs
    assert ['tb_adder_basics.in2', 'tb_adder_basics.adder.in2'] in sigs
    assert ['tb_adder_basics.rst_n', 'tb_adder_basics.adder.rst'] in sigs

    wf_paths = ['tests/files/sim/adder_toggle_together/tb_adder_basics.vcd']  # in1 and in2 are "coincidentially" equal
    sigs = find_matching_signals(wf_paths)
    assert len(sigs) == 4
    assert ['tb_adder_basics.out', 'tb_adder_basics.adder.out'] in sigs
    assert ['tb_adder_basics.clk', 'tb_adder_basics.adder.clk'] in sigs
    assert ['tb_adder_basics.in1', 'tb_adder_basics.in2', 'tb_adder_basics.adder.in1', 'tb_adder_basics.adder.in2'] in sigs
    assert ['tb_adder_basics.rst_n', 'tb_adder_basics.adder.rst'] in sigs


def test_find_matching_signals_edge_cases(no_signals: VCDWaveform) -> None:
    assert _refine_partition(None, {}) is None
    assert _refine_partition([], {}) is None

    assert partition_all_vcd_signals([]) is None

    assert partition_all_vcd_signals(['tests/files/sim/no_signals/tb_no_signals.vcd']) is None


def test_find_matching_signals_different_top_scopes(adder_vcd: VCDWaveform, wrapper_vcd: VCDWaveform) -> None:
    wf_paths = ['tests/files/sim/adder_basics/tb_adder_basics.vcd', 'tests/files/sim/adderWrapper/tb_adderWrapper.vcd']
    with pytest.raises(VcdLoadingError):
        find_matching_signals(wf_paths)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
