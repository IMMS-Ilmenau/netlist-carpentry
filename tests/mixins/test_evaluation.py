import os

import pytest

from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.mixins.evaluation import EvaluationMixin
from netlist_carpentry.core.netlist_elements.module import Module


def test_not_implemented() -> None:
    em = EvaluationMixin(raw_path='a.b.c')
    with pytest.raises(NotImplementedError):
        em.instances_with_constant_inputs
    with pytest.raises(NotImplementedError):
        em.input_ports
    with pytest.raises(NotImplementedError):
        em.get_outgoing_edges('some_inst')
    with pytest.raises(NotImplementedError):
        em.get_load_ports(WireSegmentPath(raw='a.b.c.0'))


def test_evaluate_wire_seg() -> None:
    em = Module(raw_path='a')
    em.create_wire('b')
    following_insts = em._evaluate_ws(WireSegmentPath(raw='a.b.0'))
    assert following_insts == {0} - {0}  # Funny eyes <=> empty set


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
