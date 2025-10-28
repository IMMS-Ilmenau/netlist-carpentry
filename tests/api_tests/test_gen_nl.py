import os

import pytest

from netlist_carpentry.api.read.gen_nl import generate_json_netlist

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def test_generate_json_netlist() -> None:
    files_path = f'{SCRIPT_DIR}/../files/'
    hdl_base = 'simpleAdder'
    adder_json = f'{files_path}/{hdl_base}.json'
    if os.path.exists(adder_json):
        os.remove(adder_json)
    assert not os.path.exists(adder_json)

    generate_json_netlist(files_path + 'simpleAdder.v', files_path + 'simpleAdder.json', 'simpleAdder', verbose=True)
    assert os.path.exists(adder_json)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
