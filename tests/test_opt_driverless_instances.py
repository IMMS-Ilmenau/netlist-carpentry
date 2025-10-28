import os

import pytest
from utils import connected_module

from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.opt.driverless_instances import (
    opt_driverless,
    opt_driverless_instances,
    opt_driverless_wires,
)


@pytest.fixture
def module() -> Module:
    return connected_module()


def test_opt_driverless(module: Module) -> None:
    assert len(module.wires) == 12
    assert len(module.instances) == 5
    any_removed = opt_driverless(module)  # Removes unused wire "en"
    assert any_removed
    assert len(module.wires) == 11
    assert len(module.instances) == 5

    any_removed = opt_driverless(module)  # Nothing removed
    assert not any_removed
    assert len(module.wires) == 11
    assert len(module.instances) == 5

    module.disconnect(module.ports['in1'][0])
    any_removed = opt_driverless(module)  # Nothing removed
    assert any_removed
    assert len(module.wires) == 10
    assert len(module.instances) == 5

    module.disconnect(module.ports['in2'][0])
    any_removed = opt_driverless(module)  # Removes now unused wire "out" and instance
    assert any_removed
    assert len(module.wires) == 8
    assert len(module.instances) == 4

    module.disconnect(module.ports['in3'][0])
    module.disconnect(module.ports['in4'][0])
    module.disconnect(module.ports['clk'][0])
    module.disconnect(module.ports['rst'][0])
    any_removed = opt_driverless(module)  # Removes now instances and wires, since all inputs are now unconnected
    assert any_removed
    assert len(module.wires) == 0
    assert len(module.instances) == 0


def test_opt_driverless_wires_simple(module: Module) -> None:
    assert len(module.wires) == 12
    any_removed = opt_driverless_wires(module)  # Removes unused wire "en"
    assert any_removed
    assert len(module.wires) == 11

    module.disconnect(module.ports['in1'][0])
    any_removed = opt_driverless_wires(module)  # Removes now unused wire "wire1"
    assert any_removed
    assert len(module.wires) == 10

    any_removed = opt_driverless_wires(module)  # Nothing to optimize anymore
    assert not any_removed
    assert len(module.wires) == 10


def test_opt_driverless_instances_simple(module: Module) -> None:
    assert len(module.instances) == 5
    any_removed = opt_driverless_instances(module)  # Nothing to optimize anymore
    assert not any_removed
    assert len(module.instances) == 5

    module.remove_wire('in1')
    any_removed = opt_driverless_instances(module)  # Nothing to optimize anymore
    assert not any_removed
    assert len(module.instances) == 5

    module.remove_wire('in2')
    any_removed = opt_driverless_instances(module)  # Removes now unused instance combining "in1" and "in2"
    assert any_removed
    assert len(module.instances) == 4


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])

if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
