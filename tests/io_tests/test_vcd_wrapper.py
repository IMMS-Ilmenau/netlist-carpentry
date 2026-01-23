import os
from pathlib import Path

import pytest
from pywellen import Waveform

from netlist_carpentry import read
from netlist_carpentry.io.vcd.wrapper import VCDWaveform
from tests.test_verilog import _setup_run_circuit


@pytest.fixture()
def adder_vcd() -> VCDWaveform:
    c = read('tests/files/simpleAdder.v')
    _setup_run_circuit('adder_basics', c)
    return VCDWaveform(Waveform('tests/files/sim/adder_basics/tb_adder_basics.vcd'))


def test_vcd_var(adder_vcd: VCDWaveform) -> None:
    top_scope = adder_vcd.top_scopes[0]
    scope = top_scope.scopes[0]
    var = scope.vars[0]
    assert var.name == 'clk'
    assert var.full_name == 'tb_adder_basics.adder.clk'
    assert var.bitwidth == 1
    assert var.var_type == 'Wire'
    assert var.enum_type is None
    assert var.direction == 'Unknown'
    assert var.length == 1
    assert not var.is_real
    assert not var.is_string
    assert var.is_bit_vector
    assert var.is_1bit

    assert len(var.all_changes) == 29
    assert var.all_changes[0][0] == 0
    assert var.all_changes[0][1] == 'x'
    for i in range(20):
        assert var.all_changes[i + 1][1] == i % 2
    assert len(var.change_times) == 29
    assert var.change_times[0] == 0
    assert var.change_times[1] == 610
    assert var.change_times[2] == 650
    assert var.change_times[3] == 700

    assert var.value_at_time(0) == 'x'
    assert var.value_at_time(100) == 'x'
    assert var.value_at_time(600) == 0
    assert var.value_at_time(650) == 1
    assert var.value_at_time(700) == 0

    assert var.value_at_idx(0) == 'x'
    assert var.value_at_idx(1) == 'x'  # It seems like indexing starts at 1 ??
    assert var.value_at_idx(2) == 0
    assert var.value_at_idx(3) == 1
    assert var.value_at_idx(4) == 0

    assert str(var) == 'Wire(tb_adder_basics.adder.clk)'
    assert repr(var) == 'Wire(tb_adder_basics.adder.clk)'


def test_vcd_var_changes(adder_vcd: VCDWaveform) -> None:
    for var in adder_vcd.all_vars.values():
        if var.name == 'out':
            assert len(var.all_changes) == 4
            assert var.all_changes[0] == (0, 'xxxxxxxxx')
            assert var.all_changes[1] == (310, 0)
            assert var.all_changes[2] == (650, 'xxxxxxxxx')
            assert var.all_changes[3] == (1050, 0)
            assert str(var.all_changes[3]) == '(1050, 0)'
            assert var.change_times == [0, 310, 650, 1050]
        elif var.name == '__0__out__8__0__':
            assert len(var.all_changes) == 4
            assert var.all_changes[0] == (0, 'xxxxxxxxx')
            assert var.all_changes[1] == (1350, 180)
            assert str(var.all_changes[1]) == '(1350, 180)'
            assert var.change_times == [0, 1350, 1550, 1750]
        elif var.name == 'CLK_PERIOD':
            assert len(var.all_changes) == 1
            assert var.all_changes[0] == (0, 10)
        elif var.name == 'clk':
            assert len(var.all_changes) == 29
        elif var.name == 'in1':
            assert len(var.all_changes) == 4
            assert var.all_changes[0] == (0, 'xxxxxxxx')
            assert var.all_changes[1] == (1350, 165)
        elif var.name == 'in2':
            assert len(var.all_changes) == 4
            assert var.all_changes[0] == (0, 'xxxxxxxx')
            assert var.all_changes[1] == (1350, 15)
        elif var.name == 'rst':
            assert len(var.all_changes) == 4
            assert var.all_changes[0] == (0, 'x')
            assert var.all_changes[1] == (310, 1)
            assert var.all_changes[2] == (610, 0)
            assert var.all_changes[3] == (1050, 1)
            assert str(var.all_changes[0]) == "(0, 'x')"
        elif var.name == 'WIDTH':
            assert len(var.all_changes) == 1


def test_vcd_scope(adder_vcd: VCDWaveform) -> None:
    top_scope = adder_vcd.top_scopes[0]
    scope = top_scope.scopes[0]
    assert scope.name == 'adder'
    assert scope.full_name == 'tb_adder_basics.adder'
    assert scope.scope_type == 'module'
    assert scope.scopes == []
    assert len(scope.vars) == 7

    assert str(scope) == 'module(tb_adder_basics.adder)'
    assert repr(scope) == 'module(tb_adder_basics.adder)'


def test_vcd_waveform(adder_vcd: VCDWaveform) -> None:
    assert len(adder_vcd.top_scopes) == 1
    assert len(adder_vcd.all_vars) == 13
    assert all('tb_adder_basics' in v for v in adder_vcd.all_vars)
    top_signals = [v for v in adder_vcd.all_vars if '.adder' not in v]
    adder_signals = [v for v in adder_vcd.all_vars if '.adder' in v]
    assert len(top_signals) == 6
    assert len(adder_signals) == 7
    assert any('rst' in v for v in top_signals)
    assert any('rst' in v for v in adder_signals)
    assert any('clk' in v for v in top_signals)
    assert any('clk' in v for v in adder_signals)

    assert str(adder_vcd) == 'Waveform(1 Top Scope, 13 Variables)'
    assert repr(adder_vcd) == 'Waveform(1 Top Scope, 13 Variables)'


def test_vcd_waveform_str_path() -> None:
    wf = VCDWaveform('tests/files/sim/adder_basics/tb_adder_basics.vcd')
    assert len(wf.top_scopes) == 1
    assert len(wf.all_vars) == 13

    wf = VCDWaveform(Path('tests/files/sim/adder_basics/tb_adder_basics.vcd'))
    assert len(wf.top_scopes) == 1
    assert len(wf.all_vars) == 13


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
