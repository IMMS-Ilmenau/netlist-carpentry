import os
from pathlib import Path

import pytest

from netlist_carpentry.api.read._abstract_reader import _AbstractReader


def test_adder_netlist_dict() -> None:
    r = _AbstractReader('path/to/some/file')

    assert r.path == Path('path/to/some/file')

    with pytest.raises(NotImplementedError):
        r.read()


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
