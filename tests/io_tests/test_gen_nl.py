import os
import re
from pathlib import Path

import pytest

from netlist_carpentry import ReadConfig
from netlist_carpentry.core.exceptions import YosysError
from netlist_carpentry.io.read.read_utils import generate_json, generate_json_netlist

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def test_generate_json() -> None:
    files_path = Path(f'{SCRIPT_DIR}/../files/').resolve()
    hdl_base = 'simpleAdder'
    adder_json = Path(f'{files_path}/{hdl_base}.json')
    script_path = Path(f'{files_path}/nl_gen.sh')
    if os.path.exists(adder_json):
        os.remove(adder_json)
    if os.path.exists(script_path):
        os.remove(script_path)
    assert not os.path.exists(adder_json)
    assert not os.path.exists(script_path)

    rc = ReadConfig(files=[Path(files_path) / 'simpleAdder.v'], json_path=Path(files_path) / 'simpleAdder.json', top='simpleAdder')
    p = generate_json(rc, yosys_script_path=script_path)
    assert p.returncode == 0
    assert p.stderr == ''
    assert bool(p.stdout)
    assert os.path.exists(adder_json)
    assert os.path.exists(script_path)
    os.remove(script_path)

    p = generate_json(rc, overwrite=True)
    assert p.returncode == 0
    assert p.stderr == ''
    assert bool(p.stdout)
    with pytest.raises(FileExistsError):
        generate_json(rc)


def test_generate_json_default() -> None:
    files_path = Path(f'{SCRIPT_DIR}/../files/').resolve()
    hdl_base = 'simpleAdder'
    adder_json = Path(f'{files_path}/{hdl_base}.json')
    if os.path.exists(adder_json):
        os.remove(adder_json)
    assert not os.path.exists(adder_json)

    with pytest.raises(YosysError):
        generate_json([])

    p = generate_json([Path(files_path) / 'simpleAdder.v'])
    assert p.returncode == 0
    assert p.stderr == ''
    assert bool(p.stdout)
    assert os.path.exists(adder_json)

    p = generate_json([Path(files_path) / 'simpleAdder.v'], overwrite=True)
    assert p.returncode == 0
    assert p.stderr == ''
    assert bool(p.stdout)
    with pytest.raises(FileExistsError):
        generate_json([Path(files_path) / 'simpleAdder.v'])


def test_generate_json_netlist() -> None:
    files_path = Path(f'{SCRIPT_DIR}/../files/').resolve()
    hdl_base = 'simpleAdder'
    adder_json = Path(f'{files_path}/{hdl_base}.json')
    if os.path.exists(adder_json):
        os.remove(adder_json)
    assert not os.path.exists(adder_json)

    warn_str = r"'generate_json_netlist()' is deprecated and will be removed in v1.0.0. Call `generate_json` with a `ReadConfig` object with the corresponding data (or simply with the RTL files) instead!"
    with pytest.warns(DeprecationWarning, match=re.escape(warn_str)):
        p = generate_json_netlist(Path(files_path) / 'simpleAdder.v', Path(files_path) / 'simpleAdder.json', 'simpleAdder')
    assert p.returncode == 0
    assert p.stderr == ''
    assert bool(p.stdout)
    assert os.path.exists(adder_json)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
