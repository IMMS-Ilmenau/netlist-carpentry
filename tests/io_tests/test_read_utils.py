import os
import sys
from pathlib import Path

sys.path.append('.')

import pytest

from netlist_carpentry import ReadConfig, read, read_json, read_via_cfg, read_yosys
from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.exceptions import YosysError


def test_static_read_json() -> None:
    circuit = read_json(Path('tests/files/simpleAdder.json').expanduser().resolve())
    assert circuit is not None
    assert isinstance(circuit, Circuit)
    assert len(circuit.modules) == 1
    assert 'simpleAdder' in circuit.modules
    adder = circuit['simpleAdder']
    assert len(adder.metadata['yosys']) == 3
    assert len(adder.ports) == 5
    assert len(adder.instances) == 2
    assert len(adder.wires) == 6

    assert circuit.top_name == 'simpleAdder'


def test_read_via_cfg() -> None:
    circuit = read_via_cfg(ReadConfig(files=[Path('tests/files/simpleAdder.v')], top='simpleAdder'), circuit_name='Circuit', verbose=True)
    assert circuit is not None
    assert isinstance(circuit, Circuit)
    assert circuit.name == 'Circuit'
    assert len(circuit.modules) == 1
    assert 'simpleAdder' in circuit.modules
    adder = circuit['simpleAdder']
    assert len(adder.metadata['yosys']) == 3
    assert len(adder.ports) == 5
    assert len(adder.instances) == 2
    assert len(adder.wires) == 6
    assert circuit.top_name == 'simpleAdder'

    circuit = read_via_cfg(ReadConfig(files=[Path('tests/files/simpleAdder.v')], top='simpleAdder'), verbose=True)
    assert circuit.name == 'tmp'


@pytest.mark.skipif(os.environ.get('GITHUB_ACTIONS') == 'true', reason='Skip this test on GitHub Actions only.')
def test_read_via_cfg_slang() -> None:
    rc = ReadConfig(files=[Path('tests/files/simpleAdder.v')], top='simpleAdder', yosys_plugins=['slang'])
    circuit = read_via_cfg(rc, circuit_name='Circuit', verbose=True)
    assert circuit is not None
    assert isinstance(circuit, Circuit)
    assert circuit.name == 'Circuit'
    assert len(circuit.modules) == 1
    assert 'simpleAdder' in circuit.modules
    adder = circuit['simpleAdder']
    assert len(adder.metadata['yosys']) == 2
    assert len(adder.ports) == 5
    assert len(adder.instances) == 2
    assert len(adder.wires) == 6
    assert circuit.top_name == 'simpleAdder'

    circuit = read_via_cfg(ReadConfig(files=[Path('tests/files/simpleAdder.v')], top='simpleAdder'), verbose=True)
    assert circuit.name == 'tmp'


def test_read_yosys() -> None:
    circuit = read_yosys(Path('tests/files/read_simpleAdder.ys'))
    assert isinstance(circuit, Circuit)
    assert 'simpleAdder' in circuit

    with pytest.raises(FileNotFoundError):
        read_yosys('invalid')  # Script does not exist

    match_str = r'invalid-yosys: command not found'
    with pytest.raises(YosysError, match=match_str):  # No JSON generated for invalid executable
        read_yosys(Path('tests/files/read_simpleAdder.ys'), yosys_executable='invalid-yosys')

    circuit = read_yosys(Path('tests/files/read_empty.ys'))
    assert circuit.modules == {}  # Empty circuit

    match_str = r"ERROR: File `nonexisting_file.sv' not found or is a directory"
    with pytest.raises(YosysError, match=match_str):
        read_yosys(Path('tests/files/read_invalid.ys'))


def test_static_read_verilog() -> None:
    circuit = read(Path('tests/files/simpleAdder.v'), 'simpleAdder')
    assert circuit is not None
    assert isinstance(circuit, Circuit)
    assert len(circuit.modules) == 1
    assert 'simpleAdder' in circuit.modules
    adder = circuit['simpleAdder']
    assert len(adder.metadata['yosys']) == 3
    assert len(adder.ports) == 5
    assert len(adder.instances) == 2
    assert len(adder.wires) == 6

    assert circuit.top_name == 'simpleAdder'

    with pytest.raises(ValueError):
        read(ReadConfig(files=[Path('tests/files/simpleAdder.v')]), top='simpleAdder', verbose=True)


def test_static_read_verilog_not_exist() -> None:
    with pytest.raises(YosysError):
        read('nonexistent_file.v')


def test_static_read_multiple_files() -> None:
    c = read(['tests/files/simpleAdder.v', 'tests/files/hierarchicalAdder.v'], top='hierarchicalAdder')
    hier = c.modules['hierarchicalAdder']
    assert len(c.modules) == 2
    assert 'adder' in hier.instances
    assert 'simpleAdder' in hier.instances_by_types


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
