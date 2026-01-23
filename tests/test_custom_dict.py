import os

import pytest

from netlist_carpentry.core.exceptions import IdentifierConflictError, ObjectLockedError, ObjectNotFoundError
from netlist_carpentry.utils.custom_dict import CustomDict


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
