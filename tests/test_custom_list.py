import os

import pytest

from netlist_carpentry.core.exceptions import IdentifierConflictError, ObjectLockedError, ObjectNotFoundError
from netlist_carpentry.utils.custom_list import CustomList


def test_flatten() -> None:
    nested_list = CustomList([[1, 2], [3, 4]])
    new_list = nested_list.flatten()
    assert new_list == [1, 2, 3, 4]

    nested_list = CustomList([[1, 2], 3, 4])
    new_list = nested_list.flatten()
    assert new_list == [1, 2, 3, 4]

    nested_list = CustomList([1, 2, 3, 4])
    new_list = nested_list.flatten()
    assert new_list == [1, 2, 3, 4]

    nested_list = CustomList([[1, [2]], [[[3], 4]]])
    new_list = nested_list.flatten()
    assert new_list == [1, 2, 3, 4]

    nested_list = CustomList([[], [[[]], []]])
    new_list = nested_list.flatten()
    assert new_list == []


def test_add() -> None:
    test_list: CustomList[str] = CustomList()
    added = test_list.add('foo')

    assert added == 'foo'
    assert len(test_list) == 1
    assert 'foo' in test_list

    with pytest.raises(ObjectLockedError):
        test_list.add('bar', locked=True)
    assert len(test_list) == 1
    assert 'bar' not in test_list

    with pytest.raises(IdentifierConflictError):
        test_list.add('foo')
    assert len(test_list) == 1

    added = test_list.add('foo', allow_duplicates=True)
    assert added == 'foo'
    assert len(test_list) == 2
    assert test_list.count('foo') == 2


def test_remove() -> None:
    test_list = CustomList(['foo'])
    with pytest.raises(ObjectLockedError):
        test_list.remove('foo', locked=True)
    assert 'foo' in test_list
    assert len(test_list) == 1

    test_list.remove('foo')
    assert 'foo' not in test_list
    assert len(test_list) == 0

    with pytest.raises(ObjectNotFoundError):
        test_list.remove('bar')


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
