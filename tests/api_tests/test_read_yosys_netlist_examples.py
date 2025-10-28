import os
import sys

from netlist_carpentry import CFG, LOG, read
from netlist_carpentry.utils.log import Log, initialize_logging

sys.path.append('.')

import pytest

file_path = os.path.realpath(__file__)
file_dir_path = os.path.dirname(file_path)
LOG_DIRECTORY = file_dir_path + '/../logs/'
LOG_NAME = 'log_examples.log'
LOG_PATH = LOG_DIRECTORY + LOG_NAME


@pytest.fixture
def log_setup() -> Log:
    CFG.log_level = 1
    initialize_logging(LOG_DIRECTORY, custom_file_name=LOG_NAME)
    return LOG


def test_decentral_mux(log_setup: Log) -> None:
    CFG.simplify_escaped_identifiers = True
    c = read('tests/files/decentral_mux.v')
    assert len(c.modules) == 1
    mux = c.first
    c.set_top(mux)
    assert len(mux.metadata.yosys) == 2
    assert c.top == mux
    assert len(mux.ports) == 3
    assert len(mux.instances) == 96
    assert len(mux.wires) == 67


def test_decentral_mux_no_escape(log_setup: Log) -> None:
    CFG.simplify_escaped_identifiers = False
    c = read('tests/files/decentral_mux.v')
    assert len(c.modules) == 1
    mux = c.first
    c.set_top(mux)
    assert len(mux.metadata.yosys) == 2
    assert c.top == mux
    assert len(mux.ports) == 3
    assert len(mux.instances) == 96
    assert len(mux.wires) == 67

    dI = mux.ports['DATA_I']
    assert dI.width == 16
    assert dI.offset == 0
    assert 'signed' in dI.parameters
    assert dI.parameters['signed'] == 0
    assert not dI.signed
    sI = mux.ports['SELECT_I']
    assert sI.width == 8
    assert sI.offset == 0
    assert 'signed' in sI.parameters
    assert sI.parameters['signed'] == 0
    assert not sI.signed
    dO = mux.ports['DATA_O']
    assert dO.width == 1
    assert dO.offset == 0
    assert 'signed' in dO.parameters
    assert dO.parameters['signed'] == 0
    assert not dO.signed


def test_signed_example(log_setup: Log) -> None:
    c = read('tests/files/signed_example.v')
    assert len(c.modules) == 1
    signed_module = c.first
    c.set_top(signed_module)
    assert len(signed_module.metadata.yosys) == 1
    assert c.top == signed_module
    assert len(signed_module.ports) == 3
    assert len(signed_module.instances) == 1
    assert len(signed_module.wires) == 3

    inA = signed_module.ports['inA']
    assert inA.width == 4
    assert inA.offset == 5
    assert 'signed' in inA.parameters
    assert inA.parameters['signed'] == 1
    assert inA.signed
    inB = signed_module.ports['inB']
    assert inB.width == 4
    assert inB.offset == 3
    assert 'signed' in inB.parameters
    assert inB.parameters['signed'] == 1
    assert inB.signed
    c = signed_module.ports['c']
    assert c.width == 4
    assert c.offset == 1
    assert 'signed' in c.parameters
    assert c.parameters['signed'] == 1
    assert c.signed


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
