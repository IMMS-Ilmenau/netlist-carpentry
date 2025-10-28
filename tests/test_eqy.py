import os
import shutil

import pytest
from utils import save_results

from netlist_carpentry import CFG
from netlist_carpentry.api.read.yosys_netlist import YosysNetlistReader as YNR
from netlist_carpentry.api.write.py2v import P2VTransformer as P2V
from netlist_carpentry.core.graph.constraint import CASCADING_OR_CONSTRAINT
from netlist_carpentry.core.graph.pattern_generator import PatternGenerator
from netlist_carpentry.scripts.eqy_check import EqyWrapper


def test_eqy_basics() -> None:
    eqy = EqyWrapper('some/path')
    assert str(eqy.path) == 'some/path'


def test_create_eqy_file() -> None:
    eqy_path = 'tests/files/gen/test_create_eqy_file.eqy'
    eqy = EqyWrapper(eqy_path)
    if os.path.exists(eqy_path):
        os.remove(eqy_path)
    eqy.create_eqy_file(['input_file1.v', 'input_file2.v'], 'test_top', [], '')
    assert os.path.exists(eqy_path)
    with open(eqy_path) as f:
        content = f.read()

    assert '[gold]' in content
    gold_sec = content[: content.find('[gate]')]
    assert 'read_verilog input_file1.v\n' in gold_sec
    assert 'read_verilog input_file2.v\n' in gold_sec
    assert 'prep -top test_top\n' in gold_sec
    assert '[gate]' in content
    gate_sec = content[content.find('[gate]') : content.find('[strategy sat]')]
    assert '[gate]\n\n\nmemory_map\n\n' == gate_sec
    assert '[strategy sat]' in content
    strat_sec = content[content.find('[strategy sat]') :]
    assert '[strategy sat]\nuse sat\ndepth 10' == strat_sec
    # Remove generated file if test passes, so it is only kept for analysis if the test fails
    os.remove(eqy_path)


def test_decentral_mux_eqy_creation() -> None:
    name = 'decentral_mux'
    eqy_path = f'tests/files/gen/{name}.eqy'
    eqy = EqyWrapper(eqy_path)
    eqy.create_eqy_file([f'tests/files/{name}.v'], name, [f'tests/files/gen/test_write_py2v_examples.test_{name}.v'], name)
    with open(eqy_path) as f:
        found_str = f.read()
    target_str = '[gold]\nread_verilog tests/files/decentral_mux.v\nprep -top decentral_mux\nmemory_map\n\n[gate]\nread_verilog tests/files/gen/test_write_py2v_examples.test_decentral_mux.v\nprep -top decentral_mux\nmemory_map\n\n[strategy sat]\nuse sat\ndepth 10'

    assert target_str == found_str
    # Remove generated file if test passes, so it is only kept for analysis if the test fails
    os.remove(eqy_path)


@pytest.mark.skip
def test_decentral_mux_eqy_run() -> None:
    name = 'decentral_mux'
    eqy_path = f'tests/files/gen/{name}.eqy'
    eqy_out = f'tests/files/gen/{name}'
    eqy = EqyWrapper(eqy_path)
    eqy.create_eqy_file([f'tests/files/{name}.v'], name, [f'tests/files/gen/test_write_py2v_examples.test_{name}.v'], name)

    return_code = eqy.run_eqy(eqy_out)
    assert return_code == 0  # Successful execution
    assert os.path.exists(eqy_out)

    return_code = eqy.run_eqy(eqy_out, overwrite=True)
    assert return_code == 0  # Successful execution
    assert os.path.exists(eqy_out)

    # Remove generated file and folder if test passes, so it is only kept for analysis if the test fails
    os.remove(eqy_path)
    shutil.rmtree(eqy_out, ignore_errors=True)
    assert not os.path.exists(eqy_out)


@pytest.mark.skip
def test_decentral_mux_eqy_run_remove() -> None:
    name = 'decentral_mux'
    eqy_path = f'tests/files/gen/{name}.eqy'
    eqy_out = f'tests/files/gen/{name}'
    eqy = EqyWrapper(eqy_path)
    eqy.create_eqy_file([f'tests/files/{name}.v'], name, [f'tests/files/gen/test_write_py2v_examples.test_{name}.v'], name)

    return_code = eqy.run_eqy(eqy_out, True)
    assert return_code == 0  # Successful execution
    assert not os.path.exists(eqy_out)
    # Remove generated file and folder if test passes, so it is only kept for analysis if the test fails
    os.remove(eqy_path)


@pytest.mark.skip
def test_decentral_mux_pattern_replace_eqy() -> None:
    # Create file before checking equality
    CFG.simplify_escaped_identifiers = True
    find_pattern_file = 'tests/files/or_pattern_find.v'
    replace_pattern_file = 'tests/files/or_pattern_replace.v'
    p = PatternGenerator.build_from_verilog(find_pattern_file, replace_pattern_file, constraints=[CASCADING_OR_CONSTRAINT])
    mapping = {
        ('§or§or_pattern_replace§v§30§1', 'A', -1): ('§or§or_pattern_find§v§34§1', 'A', -1),
        ('§or§or_pattern_replace§v§30§1', 'B', -1): ('§or§or_pattern_find§v§34§1', 'B', -1),
        ('§or§or_pattern_replace§v§31§2', 'A', -1): ('§or§or_pattern_find§v§36§2', 'B', -1),
        ('§or§or_pattern_replace§v§31§2', 'B', -1): ('§or§or_pattern_find§v§38§3', 'B', -1),
        ('§or§or_pattern_replace§v§32§3', 'Y', -1): ('§or§or_pattern_find§v§38§3', 'Y', -1),
    }
    p.mapping = mapping
    module = YNR('tests/files/decentral_mux.json').transform_to_circuit().first
    p.replace(module)
    save_results(P2V().module2v(module), 'v')

    name = 'decentral_mux'
    eqy_path = f'tests/files/gen/{name}_pattern_replace.eqy'
    eqy_out = f'tests/files/gen/{name}_pattern_replace'
    eqy = EqyWrapper(eqy_path)
    eqy.create_eqy_file([f'tests/files/{name}.v'], name, ['tests/files/gen/test_eqy.test_decentral_mux_pattern_replace_eqy.v'], name)

    return_code = eqy.run_eqy(eqy_out, True)
    assert return_code == 0  # Successful execution
    # Remove generated file and folder if test passes, so it is only kept for analysis if the test fails
    os.remove(eqy_path)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
