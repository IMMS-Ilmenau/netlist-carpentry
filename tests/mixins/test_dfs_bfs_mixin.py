import os

import pytest

from netlist_carpentry.core.netlist_elements.element_path import WirePath
from netlist_carpentry.core.netlist_elements.module import Module


def test_bfs_next_paths() -> None:
    m = Module(raw_path='a')
    m.create_wire('b')
    next_paths = m._bfs_next_paths(WirePath(raw='a.b'))
    assert next_paths == {0} - {0}  # Funny eyes <=> empty set


def test_dfs_next_paths() -> None:
    m = Module(raw_path='a')
    m.create_wire('b')
    next_paths = m._dfs_next_paths(WirePath(raw='a.b'))
    assert next_paths == {0} - {0}  # Funny eyes <=> empty set


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
