import os
import subprocess
from pathlib import Path

import pytest

from netlist_carpentry.scripts.script_builder import build_and_execute, build_script


def test_build_script_simple() -> None:
    build_script(Path('tests/files/test_script'), [Path('tests/files/thermo_enc.v')], Path('thermo_enc.json'))
    with open('tests/files/test_script') as f:
        content = f.read()
    assert content.startswith('#!/bin/bash')
    assert 'read_verilog' in content and 'tests/files/thermo_enc.v' in content
    assert 'hierarchy  -libdir .' in content
    assert 'memory' in content
    assert 'opt; clean; check' in content
    assert 'insbuf; proc' in content
    assert 'write_json' in content and 'thermo_enc.json' in content
    subprocess.call(['chmod', 'u+x', 'tests/files/test_script'])
    return_value = subprocess.call(['tests/files/test_script'])
    assert return_value == 0
    os.remove('tests/files/test_script')


def test_build_script_params() -> None:
    build_script(
        Path('tests/files/test_script'),
        [Path('tests/files/thermo_enc.v')],
        Path('thermo_enc.json'),
        top='thermo_enc',
        insbuf=False,
        process_memory=False,
        techmap_paths=[Path('tests/files/pmux2mux.v')],
    )
    with open('tests/files/test_script') as f:
        content = f.read()
    assert content.startswith('#!/bin/bash')
    assert 'read_verilog ' in content and '/tests/files/thermo_enc.v' in content
    assert 'hierarchy -top thermo_enc -libdir .' in content
    assert 'memory' not in content
    assert 'techmap -map' in content and 'tests/files/pmux2mux.v' in content
    assert 'opt; clean; check' in content
    assert 'insbuf; proc' not in content
    assert 'write_json' in content and 'thermo_enc.json' in content
    subprocess.call(['chmod', 'u+x', 'tests/files/test_script'])
    return_value = subprocess.call(['tests/files/test_script'])
    assert return_value == 0
    os.remove('tests/files/test_script')


def test_build_script_bad_path() -> None:
    with pytest.raises(IsADirectoryError):
        build_script(Path('tests/files/test_script'), [Path('tests/files')], Path('thermo_enc.json'))


def test_build_and_execute() -> None:
    return_data = build_and_execute(Path('tests/files/test_script'), [Path('tests/files/thermo_enc.v')], Path('thermo_enc.json'))
    assert return_data.returncode == 0
    os.remove('tests/files/test_script')


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
