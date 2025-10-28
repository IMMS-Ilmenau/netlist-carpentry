import os
import sys

sys.path.append('.')
import pytest

from netlist_carpentry import CFG, LOG, read
from netlist_carpentry.api.write.py2v import P2VTransformer
from netlist_carpentry.utils.log import initialize_logging
from tests.utils import save_results

file_path = os.path.realpath(__file__)
file_dir_path = os.path.dirname(file_path)
LOG_DIRECTORY = file_dir_path + '/../logs/'
LOG_NAME = 'log_examples_write.log'
LOG_PATH = LOG_DIRECTORY + LOG_NAME


@pytest.fixture
def log_setup():
    CFG.log_level = 1
    initialize_logging(LOG_DIRECTORY, custom_file_name=LOG_NAME)
    return LOG


def test_decentral_mux(log_setup):
    CFG.simplify_escaped_identifiers = True
    c = read('tests/files/decentral_mux.v')
    save_results(P2VTransformer().circuit2v(c), 'v')

    assert len(c.modules) == 1
    mux = c.first
    assert len(mux.instances) == 96
    assert len(mux.wires) == 67
    assert len(mux.ports) == 3


def test_edge_detector(log_setup):
    CFG.simplify_escaped_identifiers = True
    c = read('tests/files/edge_detector.v')
    save_results(P2VTransformer().circuit2v(c), 'v')
    assert len(c.modules) == 3
    ms = iter(c)
    ed_a = next(ms)
    ed_f = next(ms)
    ed_s = next(ms)
    assert len(ed_a.instances) == 12
    assert len(ed_a.wires) == 15
    assert len(ed_a.ports) == 9

    assert len(ed_f.instances) == 5
    assert len(ed_f.wires) == 8
    assert len(ed_f.ports) == 5

    assert len(ed_s.instances) == 3
    assert len(ed_s.wires) == 6
    assert len(ed_s.ports) == 5


def test_ctr_async(log_setup):
    CFG.simplify_escaped_identifiers = True
    c = read('tests/files/ctr_async.v')
    save_results(P2VTransformer().circuit2v(c), 'v')

    assert len(c.modules) == 1
    ctr = c.first
    assert len(ctr.instances) == 49
    assert len(ctr.wires) == 21
    assert len(ctr.ports) == 3


def test_thermo_enc(log_setup):
    CFG.simplify_escaped_identifiers = True
    c = read('tests/files/thermo_enc.v')
    save_results(P2VTransformer().circuit2v(c), 'v')

    assert len(c.modules) == 1
    ctr = c.first
    assert len(ctr.instances) == 64
    assert len(ctr.wires) == 19
    assert len(ctr.ports) == 2


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
