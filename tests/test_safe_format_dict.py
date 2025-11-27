import os

import pytest

from netlist_carpentry.utils.safe_format_dict import SafeFormatDict


def test_safe_format_dict() -> None:
    d = SafeFormatDict()
    assert d['lol'] == '{lol}'

    d['foo'] = 'bar'
    assert d['foo'] == 'bar'
    assert d['lol'] == '{lol}'


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
