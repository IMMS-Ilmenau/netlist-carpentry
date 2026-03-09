import os

import pytest

from netlist_carpentry import read


def test_vhdl_simple_counter() -> None:
    source_path = 'oss-cad-suite/environment' if os.environ.get('CI_SKIP_EQY') == 'true' else '~/oss_cad_suite/environment'
    try:
        c = read('tests/files/vhdl/simple_counter.vhdl', source_paths=[source_path])
        assert len(c) == 1
        assert c.has_top
        assert '§buf' in c.instances
        assert '§adff' in c.instances
        assert '§add' in c.instances
        assert len(c.instances['§buf']) == 16
        assert len(c.instances['§adff']) == 1
        assert len(c.instances['§add']) == 1
    except FileNotFoundError:
        pytest.xfail('Installation of OSS CAD SUITE failed!')


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
