import os

import pytest

from netlist_carpentry.core.port_direction import PortDirection


def test_is_input():
    assert PortDirection.IN.is_input
    assert not PortDirection.OUT.is_input
    assert PortDirection.IN_OUT.is_input
    assert not PortDirection.UNKNOWN.is_input


def test_is_output():
    assert not PortDirection.IN.is_output
    assert PortDirection.OUT.is_output
    assert PortDirection.IN_OUT.is_output
    assert not PortDirection.UNKNOWN.is_output


def test_is_defined():
    assert PortDirection.IN.is_defined
    assert PortDirection.OUT.is_defined
    assert PortDirection.IN_OUT.is_defined
    assert not PortDirection.UNKNOWN.is_defined


def test_str():
    assert str(PortDirection.IN) == 'input'
    assert str(PortDirection.OUT) == 'output'
    assert str(PortDirection.IN_OUT) == 'inout'
    assert str(PortDirection.UNKNOWN) == 'unknown'


def test_get():
    assert PortDirection.get('input') == PortDirection.IN
    assert PortDirection.get('output') == PortDirection.OUT
    assert PortDirection.get('inout') == PortDirection.IN_OUT
    assert PortDirection.get('foo') == PortDirection.UNKNOWN


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
