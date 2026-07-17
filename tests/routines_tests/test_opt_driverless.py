import os

import pytest
from utils import connected_module

from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.routines import opt_driverless
from netlist_carpentry.routines.opt.driverless import opt_driverless_instances, opt_driverless_wires
from netlist_carpentry.utils.gate_factory import and_gate


@pytest.fixture()
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

    inputless_m = Module(name='inputless_m')
    inputless_m.create_port('O', 'output')
    inst = module.create_instance(inputless_m, 'I_inputless')
    module.connect(inst.ports['O'], module.create_port('O', 'out'))
    assert 'I_inputless' in module.instances
    assert module.instances['I_inputless'] is inst
    assert len(module.instances) == 5

    any_removed = opt_driverless_instances(module)  # Does not remove inputless submodule
    assert any_removed is False
    assert 'I_inputless' in module.instances
    assert module.instances['I_inputless'] is inst
    assert len(module.instances) == 5

    and_inst = and_gate(module, 'and_inst', Y=module.create_port('AndY', 'out'))
    and_inst.ports.remove('A')
    and_inst.ports.remove('B')  # No input ports anymore
    assert 'and_inst' in module.instances
    assert module.instances['and_inst'] is and_inst
    assert len(module.instances) == 6
    any_removed = opt_driverless_instances(module)
    assert any_removed is True
    assert 'and_inst' not in module.instances
    assert len(module.instances) == 5


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])

if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
