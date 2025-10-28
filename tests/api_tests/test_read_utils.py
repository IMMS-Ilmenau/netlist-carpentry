import os
import sys

sys.path.append('.')

import pytest

from netlist_carpentry import read, read_json
from netlist_carpentry.core.circuit import Circuit


def test_static_read_json() -> None:
    circuit = read_json('tests/files/simpleAdder.json')
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


def test_static_read_verilog() -> None:
    circuit = read('tests/files/simpleAdder.v', 'simpleAdder')
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


def test_static_read_verilog_not_exist() -> None:
    with pytest.raises(RuntimeError):
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
