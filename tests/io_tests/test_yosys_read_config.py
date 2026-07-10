import os
import re
from pathlib import Path

import pytest

from netlist_carpentry import CFG, ReadConfig
from netlist_carpentry.core.exceptions import YosysError


def test_default() -> None:
    rc = ReadConfig(files=[], output=Path('/a/b/c.v'))
    assert isinstance(rc, ReadConfig)
    assert rc.files == []
    assert rc.output == Path('/a/b/c.v')
    assert rc.top is None
    assert rc.json_path is None
    assert rc.techmaps is None
    assert rc.share == 'off'
    assert rc.environments is None
    assert rc.yosys_plugins is None
    assert rc.no_hierarchy is False
    assert rc.keep_memory_cells is False
    assert rc.insbuf is True

    tmp = '{read}\n{hierarchy}\nproc; opt\n{memory}\n{techmaps}\n{share}\nopt; clean\n{insbuf}\n{write}\n'
    assert rc.script_template == tmp


def test_yosys_executable() -> None:
    rc = ReadConfig(files=[Path('tests/files/simpleAdder.v')])
    assert rc.yosys_executable == 'yosys'
    assert rc.shell_script()[0] == 'bash'
    assert rc.shell_script()[1] == '-c'
    assert rc.shell_script()[2].splitlines()[0] == 'set -e'
    assert rc.shell_script()[2].splitlines()[1] == ''
    assert rc.shell_script()[2].splitlines()[2] == 'yosys  -p "'
    tmp = CFG.yosys_executable
    CFG.yosys_executable = 'yowasp-yosys'
    rc = ReadConfig(files=[Path('tests/files/simpleAdder.v')])
    assert rc.yosys_executable == 'yowasp-yosys'
    assert rc.shell_script()[0] == 'bash'
    assert rc.shell_script()[1] == '-c'
    assert rc.shell_script()[2].splitlines()[2] == 'yowasp-yosys  -p "'
    CFG.yosys_executable = tmp


def test_some_paths() -> None:
    rc = ReadConfig(files=[Path('tests/files/yosys_file_test_dir'), Path('tests/files/nl_gen.py'), Path('invalid/path/lol')])
    with pytest.raises(YosysError, match=r"Cannot find a Yosys read pass for 'nl_gen.py': Unknown format '.py'!"):
        rc.read_pass
    rc.files.pop(1)
    with pytest.raises(YosysError, match=r'Cannot collect read commands: No file'):
        rc.read_pass
    rc.files.pop(1)
    fs = rc.read_pass.splitlines()
    assert 'ghdl -read ' in fs[0] and '/yosys_file_test_dir/a.vhdl' in fs[0]
    assert 'read_json ' in fs[1] and '/yosys_file_test_dir/b.Json' in fs[1]
    assert 'read_verilog -sv ' in fs[2] and '/yosys_file_test_dir/c.SV' in fs[2]
    assert 'read_verilog ' in fs[3] and '/yosys_file_test_dir/d.v' in fs[3]
    assert 'ghdl -read ' in fs[4] and '/yosys_file_test_dir/e.vhd' in fs[4]

    rc.files.pop(0)
    with pytest.raises(YosysError, match=r'No files to read! Input file list was empty!'):
        rc.read_pass
    Path('tests/files/empty_directory').mkdir(parents=True, exist_ok=True)
    rc.files = [Path('tests/files/empty_directory')]
    with pytest.raises(YosysError, match=re.escape('No files to read! Input file list was [tests/files/empty_directory]')):
        rc.read_pass


def test_output() -> None:
    rc = ReadConfig(files=[], output=Path('/a/b/c.v'))
    assert rc.write_pass == 'write_verilog /a/b/c.v'
    rc.output = Path('/a/b/c.sv')
    assert rc.write_pass == 'write_verilog -sv /a/b/c.sv'
    rc.output = Path('/a/b/c.json')
    assert rc.write_pass == 'write_json /a/b/c.json'
    rc.json_path = Path('/a/b/netlist.json')
    assert rc.write_pass == 'write_json /a/b/netlist.json\nwrite_json /a/b/c.json'
    rc.output = Path('/a/b/c.different_format')
    with pytest.raises(YosysError):
        rc.write_pass


def test_hierarchy() -> None:
    rc = ReadConfig(files=[], top='abc', no_hierarchy=True)
    assert rc.hierarchy_pass == 'hierarchy -top abc'
    rc.top = None
    assert rc.hierarchy_pass == ''
    rc.no_hierarchy = False
    assert rc.hierarchy_pass == 'hierarchy -auto-top'


def test_memory() -> None:
    rc = ReadConfig(files=[])
    assert rc.keep_memory_cells is False
    assert rc.memory_pass == 'memory'
    rc.keep_memory_cells = True
    assert rc.memory_pass == 'memory -nomap'


def test_techmap() -> None:
    rc = ReadConfig(files=[], techmaps=[Path('/a/b/c.v'), Path('/d/e/f.v')])
    assert rc.techmap_pass == 'techmap -map /a/b/c.v\ntechmap -map /d/e/f.v'
    rc.techmaps = []
    assert rc.techmap_pass == ''
    rc.techmaps = None
    assert rc.techmap_pass == ''


def test_share() -> None:
    rc = ReadConfig(files=[])
    assert rc.share == 'off'
    assert rc.share_pass == ''
    rc.share = 'fast'
    assert rc.share_pass == 'share -fast'
    rc.share = 'aggressive'
    assert rc.share_pass == 'share -aggressive'
    rc.share = 'invalid'
    with pytest.raises(YosysError):
        rc.share_pass  # Will fail since no such share option exists


def test_insbuf() -> None:
    rc = ReadConfig(files=[], insbuf=False)
    assert rc.insbuf is False
    assert rc.insbuf_pass == ''
    rc.insbuf = True
    assert rc.insbuf_pass == 'insbuf; proc'


def test_environment_activation() -> None:
    import netlist_carpentry.io.read.yosys.read_config

    rc = ReadConfig(files=[], environments=[Path('/a/b/c'), Path('/d/e/f')])
    assert rc.environment_activation == 'source /a/b/c\nsource /d/e/f'
    rc.environments.clear()
    assert rc.environment_activation == ''

    tmp = netlist_carpentry.io.read.yosys.read_config.ON_WINDOWS
    setattr(netlist_carpentry.io.read.yosys.read_config, 'ON_WINDOWS', True)
    assert netlist_carpentry.io.read.yosys.read_config.ON_WINDOWS is True
    assert rc.environment_activation == ''
    rc.environments = [Path('/a/b/c'), Path('/d/e/f')]
    assert rc.environment_activation == '. /a/b/c\n. /d/e/f'
    setattr(netlist_carpentry.io.read.yosys.read_config, 'ON_WINDOWS', tmp)


def test_yosys_modules() -> None:
    rc = ReadConfig(files=['tests/files/simpleAdder.v'], yosys_plugins=['ghdl', 'slang'])
    assert rc.yosys_plugins == ['ghdl', 'slang']
    assert rc.yosys_plugin_str == '-m ghdl -m slang'
    assert 'read_slang ' in rc.read_pass
    assert 'tests/files/simpleAdder.v' in rc.read_pass
    rc.yosys_plugins.clear()
    assert rc.yosys_plugin_str == ''
    rc.yosys_plugins = None
    assert rc.yosys_plugin_str == ''


def test_yosys_commands() -> None:
    rc = ReadConfig(files=[Path('tests/files/simpleAdder.v')], output=Path('a/b/c.json'))
    found_cmds = rc.yosys_commands().splitlines()
    assert 'read_verilog' in found_cmds[0] and 'tests/files/simpleAdder.v' in found_cmds[0]
    assert found_cmds[1] == 'hierarchy -auto-top'
    assert found_cmds[2] == 'proc; opt'
    assert found_cmds[3] == 'memory'
    assert found_cmds[4] == ''
    assert found_cmds[5] == ''
    assert found_cmds[6] == 'opt; clean'
    assert found_cmds[7] == 'insbuf; proc'
    assert 'write_json' in found_cmds[8] and '/a/b/c.json' in found_cmds[8]


def test_shell_script() -> None:
    rc = ReadConfig(files=[Path('tests/files/simpleAdder.v')], output=Path('a/b/c.json'))
    found_cmds = rc.shell_script()[0] == 'bash'
    found_cmds = rc.shell_script()[1] == '-c'
    found_cmds = rc.shell_script()[2].splitlines()
    # In bash script, everything is 2 (resp. 3) lines further down because of the script's startup stuff
    assert found_cmds[0] == 'set -e'
    assert found_cmds[1] == ''
    assert found_cmds[2] == 'yosys  -p "'

    assert 'read_verilog' in found_cmds[0 + 3] and 'tests/files/simpleAdder.v' in found_cmds[0 + 3]
    assert found_cmds[1 + 3] == 'hierarchy -auto-top'
    assert found_cmds[2 + 3] == 'proc; opt'
    assert found_cmds[3 + 3] == 'memory'
    assert found_cmds[4 + 3] == ''
    assert found_cmds[5 + 3] == ''
    assert found_cmds[6 + 3] == 'opt; clean'
    assert found_cmds[7 + 3] == 'insbuf; proc'
    assert 'write_json' in found_cmds[8 + 3] and '/a/b/c.json' in found_cmds[8 + 3]

    assert found_cmds[12] == '"'  # End of Yosys command string


def test_shell_script_write() -> None:
    rc = ReadConfig(files=[Path('tests/files/simpleAdder.v')], output=Path('a/b/c.json'))
    script_path = Path('tests/files/gen/shell_script.sh')
    if script_path.exists():
        os.remove(script_path)
    found_cmds = rc.shell_script(script_path)[2].splitlines()
    assert script_path.exists()
    with open(script_path) as f:
        file_cmds = f.read()
    # '#!/bin/env bash' and the empty line are not in the console commands, but in the file as shebang
    assert file_cmds.splitlines()[2:] == found_cmds
    cmd_lst = file_cmds.splitlines()
    # In bash script, everything is 2 (resp. 3) lines further down because of the script's startup stuff
    # In addition, '#!/bin/env bash' is included, since the shell script is actually written to a files,
    # so again + 2, makes a total offset of 4 (resp. 5)
    assert cmd_lst[0] == '#!/bin/env bash'
    assert cmd_lst[1] == ''
    assert cmd_lst[2] == 'set -e'
    assert cmd_lst[3] == ''
    assert cmd_lst[4] == 'yosys  -p "'

    assert 'read_verilog' in cmd_lst[0 + 5] and 'tests/files/simpleAdder.v' in cmd_lst[0 + 5]
    assert cmd_lst[1 + 5] == 'hierarchy -auto-top'
    assert cmd_lst[2 + 5] == 'proc; opt'
    assert cmd_lst[3 + 5] == 'memory'
    assert cmd_lst[4 + 5] == ''
    assert cmd_lst[5 + 5] == ''
    assert cmd_lst[6 + 5] == 'opt; clean'
    assert cmd_lst[7 + 5] == 'insbuf; proc'
    assert 'write_json' in cmd_lst[8 + 5] and '/a/b/c.json' in cmd_lst[8 + 5]

    assert cmd_lst[14] == '"'  # End of Yosys command string

    tmp = CFG.yosys_executable
    CFG.yosys_executable = 'yowasp-yosys'
    found_cmds = rc.shell_script()[2].splitlines()
    CFG.yosys_executable = tmp
    assert found_cmds[2] == 'yowasp-yosys  -p "'


def test_shell_script_write_windows() -> None:
    import netlist_carpentry.io.read.yosys.read_config

    tmp = netlist_carpentry.io.read.yosys.read_config.ON_WINDOWS
    setattr(netlist_carpentry.io.read.yosys.read_config, 'ON_WINDOWS', True)
    assert netlist_carpentry.io.read.yosys.read_config.ON_WINDOWS is True
    rc = ReadConfig(files=[Path('tests/files/simpleAdder.v')], output=Path('a/b/c.json'))
    script_path = Path('tests/files/gen/shell_script.sh')
    if script_path.exists():
        os.remove(script_path)
    assert rc.shell_script(script_path)[0] == 'powershell.exe'
    assert rc.shell_script(script_path)[1] == '-NoProfile'
    assert rc.shell_script(script_path)[2] == '-ExecutionPolicy'
    assert rc.shell_script(script_path)[3] == 'Bypass'
    assert rc.shell_script(script_path)[4] == '-Command'
    found_cmds = rc.shell_script(script_path)[5].splitlines()
    assert script_path.exists()
    with open(script_path) as f:
        file_cmds = f.read()
    assert file_cmds.splitlines() == found_cmds
    # In windows powershell script, everything is 3 lines further down because of the script's startup stuff
    assert found_cmds[0] == "$ErrorActionPreference = 'Stop'"
    assert found_cmds[1] == ''
    assert found_cmds[2] == 'yosys  -p "'

    assert 'read_verilog' in found_cmds[0 + 3] and 'tests/files/simpleAdder.v' in found_cmds[0 + 3]
    assert found_cmds[1 + 3] == 'hierarchy -auto-top'
    assert found_cmds[2 + 3] == 'proc; opt'
    assert found_cmds[3 + 3] == 'memory'
    assert found_cmds[4 + 3] == ''
    assert found_cmds[5 + 3] == ''
    assert found_cmds[6 + 3] == 'opt; clean'
    assert found_cmds[7 + 3] == 'insbuf; proc'
    assert 'write_json' in found_cmds[8 + 3] and '/a/b/c.json' in found_cmds[8 + 3]

    assert found_cmds[12] == '"'  # End of Yosys command string

    tmp_yosys = CFG.yosys_executable
    CFG.yosys_executable = 'yowasp-yosys'
    found_cmds = rc.shell_script()[5].splitlines()
    CFG.yosys_executable = tmp_yosys
    assert found_cmds[2] == 'yowasp-yosys  -p "'
    setattr(netlist_carpentry.io.read.yosys.read_config, 'ON_WINDOWS', tmp)


def test_example() -> None:
    rc = ReadConfig(
        files=[Path('tests/files/simpleAdder.v'), Path('tests/files/hierarchicalAdder.v')],
        output=Path('tests/files/gen/read_config.SV'),
        top='hierarchicalAdder',
        json_path=Path('tests/files/gen/read_config.json'),
        share='aggressive',
        keep_memory_cells=True,
    )

    p1 = Path('tests/files/simpleAdder.v').expanduser().resolve().as_posix()
    p2 = Path('tests/files/hierarchicalAdder.v').expanduser().resolve().as_posix()
    p3 = Path('tests/files/gen/read_config.json').expanduser().resolve().as_posix()
    p4 = Path('tests/files/gen/read_config.SV').expanduser().resolve().as_posix()
    target_str = f"""read_verilog {p1}
read_verilog {p2}
hierarchy -top hierarchicalAdder
proc; opt
memory -nomap

share -aggressive
opt; clean
insbuf; proc
write_json {p3}
write_verilog -sv {p4}
"""
    found_str = rc.yosys_commands()

    assert rc.yosys_executable == 'yosys'
    assert target_str == found_str
    tmp = CFG.yosys_executable
    CFG.yosys_executable = 'yowasp-yosys'
    found_str = rc.yosys_commands()
    assert rc.yosys_executable == 'yowasp-yosys'
    CFG.yosys_executable = tmp
    assert rc.yosys_executable == 'yosys'
    assert target_str == found_str


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
