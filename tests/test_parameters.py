import os

import pytest

from netlist_carpentry import Instance, Module
from netlist_carpentry.utils.gate_lib_dataclasses import InstanceParams, Parameters


@pytest.fixture
def module() -> Module:
    m = Module(name='m')
    m.create_port('A', 'in')
    m.create_port('Y', 'out')
    return m


def test_parameters() -> None:
    p = Parameters()
    assert len(p) == 0
    assert p.as_dict() == {}
    assert p.get('invalid') is None
    assert p.get('invalid', False) is False
    assert 'invalid' not in p
    assert p.items() == []
    with pytest.raises(KeyError):
        p['invalid']
    p['new'] = True
    assert p['new'] is True
    assert 'new' in p
    assert len(p) == 1
    assert p.items() == [('new', True)]


def test_instance_params() -> None:
    p = InstanceParams()
    assert p._parent is None
    i = Instance(name='i', parameters=p, instance_type='inst')
    assert p._parent is i


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
