import os

import pytest

from netlist_carpentry import Circuit, Direction, Module
from netlist_carpentry.routines.dft.scan_chain_insertion import (
    _implement_scanff_in_submodules,
    connect_all_scan_elements,
    create_scan_ports,
    implement_scan_chain,
    replace_ff_with_scan_ff,
    skip_module,
)


@pytest.fixture()
def dff_circuit() -> Circuit:
    from utils import dff_circuit

    return dff_circuit()


@pytest.fixture()
def empty_module() -> Module:
    from utils import empty_module as esm

    return esm()


def test_create_scan_ports(dff_circuit: Circuit) -> None:
    m22 = dff_circuit['M22']

    create_scan_ports(m22, 'SCAN_ENABLE', 'SI')
    assert 'SCAN_ENABLE' in m22.ports
    assert m22.ports['SCAN_ENABLE'].width == 1
    assert m22.ports['SCAN_ENABLE'].direction == Direction.IN
    assert 'SI' in m22.ports
    assert m22.ports['SI'].width == 1
    assert m22.ports['SI'].direction == Direction.IN
    assert 'SO' in m22.ports
    assert m22.ports['SO'].width == 1
    assert m22.ports['SO'].direction == Direction.OUT

    m2 = dff_circuit['M2']
    assert 'm22' in m2.instances
    assert m2.instances['m22'].instance_type == 'M22'
    assert m2.instances['m22'].module_definition is m22
    assert 'SCAN_ENABLE' in m2.instances['m22'].ports
    assert 'SI' in m2.instances['m22'].ports
    assert 'SO' in m2.instances['m22'].ports
    assert m2.instances['m22'].ports['SCAN_ENABLE'].is_unconnected
    assert m2.instances['m22'].ports['SI'].is_unconnected
    assert m2.instances['m22'].ports['SO'].is_unconnected


def test_replace_ff_with_scan_ff(dff_circuit: Circuit) -> None:
    top = dff_circuit.top
    top.flatten(recursive=True)
    dffs = top.get_instances(type='dff', fuzzy=True)
    scans = top.get_instances(type='scan', fuzzy=True)
    assert len(dffs) == 2 * 2 + 1 + 1 + 3  # 2*M1 + M2 + M21 + 3 in M22
    assert len(scans) == 0
    return_scans = replace_ff_with_scan_ff(top)  # Also splits n-bit FF into n 1-bit FF

    dffs = top.get_instances(type='dff', fuzzy=True)
    scans = top.get_instances(type='scan', fuzzy=True)
    assert return_scans == scans
    assert len(dffs) == 2 * 2 + 1 + 1 + (1 + 2 * 8)  # Scan-DFF still are dff
    assert len(scans) == 2 * 2 + 1 + 1 + (1 + 2 * 8)  # 2*M1 + M2 + M21 + 3 in M22, but the 8-bit FF were split
    for dff in ['§dff', '§adff', '§dffe', '§adffe']:
        assert dff not in top.instances


def test_skip_module(empty_module: Module, dff_circuit: Circuit) -> None:
    assert skip_module(empty_module)

    top = dff_circuit.top
    assert not skip_module(top)

    top.metadata.set('insertion_in_progress', True, 'scan_chains')
    assert skip_module(top)


def test_implement_scan_chain(dff_circuit: Circuit) -> None:
    top = dff_circuit.top
    implement_scan_chain(top)
    dff = top.get_instances(type='§dff', recursive=True)
    adff = top.get_instances(type='§adff', recursive=True)
    dffe = top.get_instances(type='§dffe', recursive=True)
    adffe = top.get_instances(type='§adffe', recursive=True)
    assert len(dff) == 0
    assert len(adff) == 0
    assert len(dffe) == 0
    assert len(adffe) == 0
    for m in dff_circuit:
        assert 'SE' in m.ports
        assert 'SI' in m.ports
        assert 'SO' in m.ports
        assert m.ports['SE'].is_connected
        assert m.ports['SI'].is_connected
        assert m.ports['SO'].is_connected


def test_implement_scan_chain_corner_case(dff_circuit: Circuit) -> None:
    top = dff_circuit.top
    m4 = dff_circuit.create_module('M4')
    top.create_instance(m4, 'm4')
    implement_scan_chain(top)
    assert 'SE' not in m4.ports
    assert 'SI' not in m4.ports
    assert 'SO' not in m4.ports
    assert 'SE' not in top.instances['m4'].ports
    assert 'SI' not in top.instances['m4'].ports
    assert 'SO' not in top.instances['m4'].ports

    connect_all_scan_elements(top, [], 'SI', 'SO', 'SE')

    m4.create_instance(Module(raw_path='M5'), 'm5')
    scan_list = _implement_scanff_in_submodules(m4)
    assert scan_list == []


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
