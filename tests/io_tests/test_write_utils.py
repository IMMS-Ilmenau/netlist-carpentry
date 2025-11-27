import os
import re
import sys

sys.path.append('.')

import pytest

from netlist_carpentry import read, write
from netlist_carpentry.core.circuit import Circuit


def test_static_write_verilog() -> None:
    circuit = read('tests/files/simpleAdder.v', 'simpleAdder')
    assert circuit is not None
    assert isinstance(circuit, Circuit)

    if os.path.exists('./tests/files/simpleAdder_testWrite.v'):
        os.remove('./tests/files/simpleAdder_testWrite.v')
    assert not os.path.exists('./tests/files/simpleAdder_testWrite.v')
    write(circuit, output_file_path='tests/files/simpleAdder_testWrite.v', overwrite=True)
    assert os.path.exists('./tests/files/simpleAdder_testWrite.v')

    with pytest.raises(FileExistsError):
        write(circuit, output_file_path='tests/files/simpleAdder_testWrite.v')
    os.remove('./tests/files/simpleAdder_testWrite.v')

    circuit = read('tests/files/simpleAdder.v')
    circuit_name = re.sub(r'[^A-Za-z0-9]+', '_', circuit.name)
    write(circuit, output_file_path='tests/files/', overwrite=True)
    assert os.path.exists(f'./tests/files/{circuit_name}.v')
    os.remove(f'./tests/files/{circuit_name}.v')


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
