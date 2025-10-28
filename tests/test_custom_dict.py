import os

import pytest

from netlist_carpentry.core.exceptions import IdentifierConflictError, ObjectLockedError, ObjectNotFoundError
from netlist_carpentry.utils.custom_dict import CustomDict


def test_append_or_create() -> None:
    test_dict = CustomDict({'A': ['lol'], 'B': []})
    test_dict.append_or_create('A', 'lol2')
    assert test_dict['A'] == ['lol', 'lol2']

    test_dict.append_or_create('B', 'lol3')
    assert test_dict['B'] == ['lol3']

    test_dict.append_or_create('C', 'lol4')
    assert test_dict['C'] == ['lol4']

    test_dict['D'] = 'foo'
    with pytest.raises(ValueError):
        test_dict.append_or_create('D', 'lol5')


def test_update_or_create() -> None:
    test_dict = CustomDict({'A': {1: 'lol'}, 'B': {}})
    test_dict.update_or_create('A', {2: 'lol2'})
    assert test_dict['A'] == {1: 'lol', 2: 'lol2'}

    test_dict.update_or_create('A', {2: 'lol3'})
    assert test_dict['A'] == {1: 'lol', 2: 'lol3'}

    test_dict.update_or_create('B', {1: 'lol3'})
    assert test_dict['B'] == {1: 'lol3'}

    test_dict.update_or_create('C', {1: 'lol4'})
    assert test_dict['C'] == {1: 'lol4'}

    test_dict['D'] = 'foo'
    with pytest.raises(ValueError):
        test_dict.update_or_create('D', {1: 'lol5'})


def test_add() -> None:
    test_dict = CustomDict()
    added = test_dict.add('A', 'foo')

    assert added == 'foo'
    assert len(test_dict) == 1
    assert test_dict['A'] == 'foo'

    with pytest.raises(IdentifierConflictError):
        test_dict.add('A', 'bar')
    assert len(test_dict) == 1
    assert test_dict['A'] == 'foo'

    with pytest.raises(ObjectLockedError):
        test_dict.add('B', 'baz', locked=True)
    assert len(test_dict) == 1
    assert 'B' not in test_dict


def test_remove() -> None:
    test_dict = CustomDict({'A': 'foo'})
    with pytest.raises(ObjectLockedError):
        test_dict.remove('A', locked=True)
    assert 'A' in test_dict
    assert len(test_dict) == 1

    test_dict.remove('A')
    assert 'A' not in test_dict
    assert len(test_dict) == 0

    with pytest.raises(ObjectNotFoundError):
        test_dict.remove('A')
    assert len(test_dict) == 0


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
