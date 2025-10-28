import os

import pytest

from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.mixins.module_base import ModuleBaseMixin


def test_not_implemented() -> None:
    em = ModuleBaseMixin(raw_path='a.b.c')
    with pytest.raises(NotImplementedError):
        em.instances
    with pytest.raises(NotImplementedError):
        em.ports
    with pytest.raises(NotImplementedError):
        em.wires
    with pytest.raises(NotImplementedError):
        em.get_from_path(WireSegmentPath(raw='a.b.c.0'))
    with pytest.raises(NotImplementedError):
        em.is_in_module(WireSegmentPath(raw='a.b.c.0'))


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
