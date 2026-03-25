import os
import shutil

import pytest
from utils import save_results

from netlist_carpentry import read, run_equiv, run_eqy
from netlist_carpentry.core.graph.constraint import CASCADING_OR_CONSTRAINT
from netlist_carpentry.core.graph.pattern_generator import PatternGenerator
from netlist_carpentry.io.read.yosys_netlist import YosysNetlistReader as YNR
from netlist_carpentry.io.write.py2v import P2VTransformer as P2V
from netlist_carpentry.scripts.equivalence_checking import EquivalenceChecking


def test_eqy_basics() -> None:
    eqy = EquivalenceChecking([], '', [], '', 'some/path')
    assert str(eqy.script_path) == 'some/path'

    eqy._create_eqy_file()
    with pytest.raises(FileExistsError):
        eqy._create_eqy_file()
    if os.path.exists('some/path'):
        shutil.rmtree('some')


def test_create_eqy_file() -> None:
    eqy_path = 'tests/files/gen/test_create_eqy_file.eqy'
    eqy = EquivalenceChecking(['input_file1.v', 'input_file2.v'], 'test_top', [], None, eqy_path)
    if os.path.exists(eqy_path):
        os.remove(eqy_path)
    eqy._create_eqy_file(overwrite=True)
    assert os.path.exists(eqy_path)
    with open(eqy_path) as f:
        content = f.read()

    assert '[gold]' in content
    gold_sec = content[: content.find('[gate]')]
    assert 'read_verilog input_file1.v\n' in gold_sec
    assert 'read_verilog input_file2.v\n' in gold_sec
    assert 'prep -top test_top -flatten\n' in gold_sec
    assert '[gate]' in content
    gate_sec = content[content.find('[gate]') : content.find('[strategy sat]')]
    assert '[gate]\n\nprep -auto-top -flatten\nmemory_map\n\n' == gate_sec
    assert '[strategy sat]' in content
    strat_sec = content[content.find('[strategy sat]') :]
    assert '[strategy sat]\nuse sat\ndepth 10' == strat_sec
    # Remove generated file if test passes, so it is only kept for analysis if the test fails
    os.remove(eqy_path)


def test_decentral_mux_eqy_creation() -> None:
    name = 'decentral_mux'
    eqy_path = f'tests/files/gen/{name}.eqy'
    eqy = EquivalenceChecking([f'tests/files/{name}.v'], name, [f'tests/files/gen/test_write_py2v_examples.test_{name}.v'], name, eqy_path)
    eqy._create_eqy_file()
    with open(eqy_path) as f:
        found_str = f.read()
    target_str = '[gold]\nread_verilog tests/files/decentral_mux.v\nprep -top decentral_mux -flatten\nmemory_map\n\n[gate]\nread_verilog tests/files/gen/test_write_py2v_examples.test_decentral_mux.v\nprep -top decentral_mux -flatten\nmemory_map\n\n[strategy sat]\nuse sat\ndepth 10'

    assert target_str == found_str
    # Remove generated file if test passes, so it is only kept for analysis if the test fails
    os.remove(eqy_path)


def test_decentral_mux_eqy_run() -> None:
    name = 'decentral_mux'
    eqy_path = f'tests/files/gen/{name}.eqy'
    eqy_out = f'tests/files/gen/{name}'
    shutil.rmtree(eqy_out, ignore_errors=True)
    eqy = EquivalenceChecking([f'tests/files/{name}.v'], name, [f'tests/files/gen/test_write_py2v_examples.test_{name}.v'], name, eqy_path)

    process = eqy.run_eqy(eqy_out)
    assert process.returncode == 0  # Successful execution
    assert os.path.exists(eqy_out)

    # Now use "standalone" function, and check overwrite param
    process = run_eqy(
        [f'tests/files/{name}.v'],
        [f'tests/files/gen/test_write_py2v_examples.test_{name}.v'],
        name,
        name,
        script_path=eqy_path,
        output_path=eqy_out,
        overwrite=True,
    )
    assert process.returncode == 0  # Successful execution
    assert os.path.exists(eqy_out)

    # Remove generated file and folder if test passes, so it is only kept for analysis if the test fails
    os.remove(eqy_path)
    shutil.rmtree(eqy_out, ignore_errors=True)
    assert not os.path.exists(eqy_out)


@pytest.mark.skip  # @pytest.mark.skipif(os.environ.get('CI_SKIP_EQY') == 'true', reason='EQY missing in CI')
def test_decentral_mux_pattern_replace_eqy() -> None:
    # Create file before checking equality
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
    read('tests/files/decentral_mux.v', out='tests/files/')
    module = YNR('tests/files/decentral_mux.json').transform_to_circuit().first
    p.replace(module)
    save_results(P2V().module2v(module), 'v')

    name = 'decentral_mux'
    eqy_path = f'tests/files/gen/{name}_pattern_replace.eqy'
    eqy_out = f'tests/files/gen/{name}_pattern_replace'
    eqy = EquivalenceChecking(eqy_path)
    eqy._create_eqy_file([f'tests/files/{name}.v'], name, ['tests/files/gen/test_eqy.test_decentral_mux_pattern_replace_eqy.v'], name)

    return_code = eqy.run_eqy(eqy_out, True)
    assert return_code == 0  # Successful execution
    # Remove generated file and folder if test passes, so it is only kept for analysis if the test fails
    os.remove(eqy_path)


def test_run_equiv_simple() -> None:
    equiv_proc = run_equiv('tests/files/or_pattern_find.v', 'tests/files/or_pattern_replace.v', 'or_pattern_find', 'or_pattern_replace', quiet=False)
    assert equiv_proc.returncode == 0
    assert equiv_proc.stdout is None  # No piping, instead shown in the console
    assert equiv_proc.stderr is None  # No piping, instead shown in the console

    equiv_proc = run_equiv('tests/files/or_pattern_find.v', 'tests/files/simple_or_structure.v', 'or_pattern_find', 'simple_or_structure', quiet=True)
    assert equiv_proc.returncode == 1
    assert equiv_proc.stdout is not None  # Output piped to stdout variable
    assert b'ERROR' in equiv_proc.stderr  # Errors piped to stderr variable


def test_run_equiv_circuit() -> None:
    gold = read('tests/files/or_pattern_find.v', 'or_pattern_find')
    gate = read('tests/files/or_pattern_replace.v', 'or_pattern_replace')
    equiv_proc = run_equiv(gold, gate, quiet=False)
    assert equiv_proc.returncode == 0
    assert equiv_proc.stdout is None  # No piping, instead shown in the console
    assert equiv_proc.stderr is None  # No piping, instead shown in the console

    equiv_proc = run_equiv(gold, gate, quiet=True)
    assert equiv_proc.returncode == 0
    assert equiv_proc.stdout is not None
    assert equiv_proc.stderr == b''


def test_run_eqy_circuit() -> None:
    gold = read('tests/files/or_pattern_find.v', 'or_pattern_find')
    gate = read('tests/files/or_pattern_find.v', 'or_pattern_find')
    equiv_proc = run_eqy(gold, gate, quiet=False)
    assert equiv_proc.returncode == 0
    assert equiv_proc.stdout is None  # No piping, instead shown in the console
    assert equiv_proc.stderr is None  # No piping, instead shown in the console

    gate = read('tests/files/or_pattern_replace.v', 'or_pattern_replace')
    equiv_proc = run_eqy(gold, gate, quiet=True)  # Different top module names let EQY fail
    assert equiv_proc.returncode == 1
    assert equiv_proc.stdout is not None
    assert b'ERROR: Failed to combine designs. For details see ' in equiv_proc.stderr
    assert b"/combine.log'.\n" in equiv_proc.stderr


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
