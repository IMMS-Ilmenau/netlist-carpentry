import os

import pytest

from netlist_carpentry import read


@pytest.mark.skipif(os.environ.get('CI_SKIP_EQY') == 'true', reason='OSS CAD SUITE missing in CI')
def test_vhdl_simple_counter() -> None:
    c = read('tests/files/vhdl/simple_counter.vhdl', source_paths=['~/oss_cad_suite/environment'])
    assert len(c) == 1
    assert c.has_top
    assert '§buf' in c.instances
    assert '§adff' in c.instances
    assert '§add' in c.instances
    assert len(c.instances['§buf']) == 16
    assert len(c.instances['§adff']) == 1
    assert len(c.instances['§add']) == 1


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
