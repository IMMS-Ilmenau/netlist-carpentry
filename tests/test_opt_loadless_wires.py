import os

import pytest
from utils import connected_module

from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.opt.loadless_wires import opt_loadless, opt_loadless_instances, opt_loadless_wires


@pytest.fixture
def module() -> Module:
    return connected_module()


def test_opt_loadless(module: Module) -> None:
    assert len(module.wires) == 12
    assert len(module.instances) == 5
    any_removed = opt_loadless(module)  # Removes unused wire "en"
    assert any_removed
    assert len(module.wires) == 11
    assert len(module.instances) == 5

    any_removed = opt_loadless(module)  # Nothing removed
    assert not any_removed
    assert len(module.wires) == 11
    assert len(module.instances) == 5

    module.disconnect(module.ports['out'][0])
    any_removed = opt_loadless(module)  # Removes now unused wire "out" and instance
    assert any_removed
    assert len(module.wires) == 10
    assert len(module.instances) == 4

    module.disconnect(module.ports['out_ff'][0])
    any_removed = opt_loadless(module)  # Removes now unused wire "out_ff" and all connected instances
    assert any_removed
    assert len(module.wires) == 0
    assert len(module.instances) == 0


def test_opt_loadless_wires_simple(module: Module) -> None:
    assert len(module.wires) == 12
    any_removed = opt_loadless_wires(module)  # Removes unused wire "en"
    assert any_removed
    assert len(module.wires) == 11

    module.disconnect(module.ports['out'][0])
    any_removed = opt_loadless_wires(module)  # Removes now unused wire "out"
    assert any_removed
    assert len(module.wires) == 10

    any_removed = opt_loadless_wires(module)  # Nothing to optimize anymore
    assert not any_removed
    assert len(module.wires) == 10


def test_opt_loadless_instances_simple(module: Module) -> None:
    assert len(module.instances) == 5
    any_removed = opt_loadless_instances(module)  # Nothing to optimize anymore
    assert not any_removed
    assert len(module.instances) == 5

    module.remove_wire('out')
    any_removed = opt_loadless_instances(module)  # Removes now unused wire "out"
    assert any_removed
    assert len(module.instances) == 4


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
