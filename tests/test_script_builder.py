import os
import re
import subprocess
from pathlib import Path

import pytest

from netlist_carpentry import CFG, ON_WINDOWS, ReadConfig
from netlist_carpentry.scripts.script_builder import build_and_execute, build_script, get_yosys_cmds, render_bash_script


def test_build_script_simple() -> None:
    assert CFG.yosys_executable == 'yosys'
    warn_str = "'build_script()' is deprecated and will be removed in v1.0.0. Create a `ReadConfig` object with the corresponding data and call `shell_script(script_path)` on it instead!"
    with pytest.warns(DeprecationWarning, match=re.escape(warn_str)):
        build_script(Path('tests/files/test_script'), [Path('tests/files/thermo_enc.v')], Path('thermo_enc.json'), no_hierarchy=True)
    with open('tests/files/test_script') as f:
        content = f.read()
    if ON_WINDOWS:
        assert content.startswith("$ErrorActionPreference = 'Stop'")
    else:
        assert content.startswith('#!/bin/env bash')

    assert 'read_verilog' in content and 'tests/files/thermo_enc.v' in content
    assert 'hierarchy' not in content
    assert 'memory' in content
    assert 'opt; clean' in content
    assert 'insbuf; proc' in content
    assert 'write_json' in content and 'thermo_enc.json' in content
    path = Path('tests/files/test_script')
    path.chmod(path.stat().st_mode | 0o111)
    return_value = subprocess.call(['tests/files/test_script'])
    assert return_value == 0
    os.remove('tests/files/test_script')


def test_build_script_params() -> None:
    import netlist_carpentry

    setattr(netlist_carpentry, 'ON_WINDOWS', False)
    warn_str = "'build_script()' is deprecated and will be removed in v1.0.0. Create a `ReadConfig` object with the corresponding data and call `shell_script(script_path)` on it instead!"
    with pytest.warns(DeprecationWarning, match=re.escape(warn_str)):
        build_script(
            Path('tests/files/test_script'),
            [Path('tests/files/thermo_enc.v')],
            Path('thermo_enc.json'),
            top='thermo_enc',
            insbuf=False,
            process_memory=False,
            share=True,
            techmap_paths=[Path('tests/files/pmux2mux.v')],
        )
    with open('tests/files/test_script') as f:
        content = f.read()
    if ON_WINDOWS:
        assert content.startswith("$ErrorActionPreference = 'Stop'")
    else:
        assert content.startswith('#!/bin/env bash')
    assert 'read_verilog ' in content and '/tests/files/thermo_enc.v' in content
    assert 'hierarchy -top thermo_enc' in content
    assert 'memory -nomap' in content
    assert 'techmap -map' in content and 'tests/files/pmux2mux.v' in content
    assert 'share -aggressive' in content
    assert 'opt; clean' in content
    assert 'insbuf; proc' not in content
    assert 'write_json' in content and 'thermo_enc.json' in content
    path = Path('tests/files/test_script')
    path.chmod(path.stat().st_mode | 0o111)
    return_value = subprocess.call(['tests/files/test_script'])
    assert return_value == 0
    os.remove('tests/files/test_script')


def test_build_script_bad_path() -> None:
    warn_str = "'build_script()' is deprecated and will be removed in v1.0.0. Create a `ReadConfig` object with the corresponding data and call `shell_script(script_path)` on it instead!"
    with pytest.warns(DeprecationWarning, match=re.escape(warn_str)):
        with pytest.raises(IsADirectoryError):
            build_script(Path('tests/files/test_script'), [Path('tests/files')], Path('thermo_enc.json'))


def test_get_yosys_cmds() -> None:
    warn_str = "'get_yosys_cmds()' is deprecated and will be removed in v1.0.0. Create a `ReadConfig` object with the corresponding data and call `yosys_commands()` on it instead!"
    with pytest.warns(DeprecationWarning, match=re.escape(warn_str)):
        cmds = get_yosys_cmds([Path('tests/files/thermo_enc.v')], Path('thermo_enc.json'))
    assert cmds == ReadConfig(files=[Path('tests/files/thermo_enc.v')], output=Path('thermo_enc.json')).yosys_commands()


def test_render_bash_script() -> None:
    script = Path('tests/files/gen/bash_script')
    if script.exists():
        os.remove(script)
    warn_str = "'render_bash_script()' is deprecated and will be removed in v1.0.0. Create a `ReadConfig` object with the corresponding data and call `shell_script(script_path)` on it instead!"
    with pytest.warns(DeprecationWarning, match=re.escape(warn_str)):
        render_bash_script(script, 'source path/to/env', 'read_verilog abcd.v', '-m ghdl ')
    target = """#!/bin/env bash\n\nset -e\n\nsource path/to/env\nyosys -m ghdl -p "read_verilog abcd.v"
"""
    assert script.exists()
    with open(script) as f:
        assert target == f.read()


def test_build_and_execute() -> None:
    return_data = build_and_execute(Path('tests/files/test_script'), [Path('tests/files/thermo_enc.v')], Path('thermo_enc.json'))
    assert return_data.returncode == 0
    os.remove('tests/files/test_script')


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
