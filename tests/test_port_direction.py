import os

import pytest

from netlist_carpentry.core.enums.direction import Direction


def test_is_input():
    assert Direction.IN.is_input
    assert not Direction.OUT.is_input
    assert Direction.IN_OUT.is_input
    assert not Direction.UNKNOWN.is_input


def test_is_output():
    assert not Direction.IN.is_output
    assert Direction.OUT.is_output
    assert Direction.IN_OUT.is_output
    assert not Direction.UNKNOWN.is_output


def test_is_defined():
    assert Direction.IN.is_defined
    assert Direction.OUT.is_defined
    assert Direction.IN_OUT.is_defined
    assert not Direction.UNKNOWN.is_defined


def test_str():
    assert str(Direction.IN) == 'input'
    assert str(Direction.OUT) == 'output'
    assert str(Direction.IN_OUT) == 'inout'
    assert str(Direction.UNKNOWN) == 'unknown'


def test_get():
    assert Direction.get('input') == Direction.IN
    assert Direction.get('output') == Direction.OUT
    assert Direction.get('inout') == Direction.IN_OUT
    assert Direction.get('foo') == Direction.UNKNOWN


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
