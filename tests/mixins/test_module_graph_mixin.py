import os

import pytest

from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.mixins.graph_building import GraphBuildingMixin


def test_not_implemented() -> None:
    em = GraphBuildingMixin(raw_path='a.b.c')
    with pytest.raises(NotImplementedError):
        em.get_driving_ports(WireSegmentPath(raw='a.b.c.0'))
    with pytest.raises(NotImplementedError):
        em.get_load_ports(WireSegmentPath(raw='a.b.c.0'))


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
