import os

import pytest

import netlist_carpentry.utils.gate_lib as lib
import netlist_carpentry.utils.gate_lib_factory as factory
from netlist_carpentry.core.exceptions import MultipleDriverError, WidthMismatchError
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.core.port_direction import PortDirection
from netlist_carpentry.utils.log import LOG


@pytest.fixture
def module() -> Module:
    from utils import empty_module

    m = empty_module()
    m.create_port('P1', direction=PortDirection.IN, width=4)
    m.create_port('P2', direction=PortDirection.IN, width=4)
    m.create_port('P3', direction=PortDirection.OUT, width=4)
    return m


def test_update_params(module: Module) -> None:
    test_params = {'width': 1}
    ports = [module.ports['P1']]
    with pytest.raises(WidthMismatchError):
        factory._update_params(test_params, ports)

    update_params = {}
    factory._update_params(update_params, ports)
    assert update_params == {'width': 4}

    update_params = {}
    factory._update_params(update_params, [])
    assert update_params == {'width': 1}

    update_params = {'width': 4}
    factory._update_params(update_params, [])
    assert update_params == {'width': 4}


def test_un_gate(module: Module) -> None:
    module.create_port('P4', direction=PortDirection.IN)
    with pytest.raises(WidthMismatchError):
        factory._un_gate(lib.NotGate, module, A=module.ports['P1'], Y=module.ports['P4'])
    module.create_port('P5', direction=PortDirection.IN, width=4)
    with pytest.raises(MultipleDriverError):
        factory._un_gate(lib.NotGate, module, A=module.ports['P1'], Y=module.ports['P5'])

    module.instances.clear()
    g = factory._un_gate(lib.NotGate, module)
    assert isinstance(g, lib.NotGate)
    assert g.name == '_NotGate_0_'
    assert g.width == 1
    assert g.ports['A'].is_unconnected
    assert g.ports['Y'].is_unconnected

    g = factory._un_gate(lib.NotGate, module, A=module.ports['P1'], Y=module.ports['P3'], params={})
    assert g.name == '_NotGate_1_'
    assert g.width == 4
    assert g.ports['A'].is_connected
    assert next(iter(g.ports['A'].connected_wires)).raw == 'test_module1._ncgen_0_'
    assert g.ports['A'].connected_wires == module.ports['P1'].connected_wires
    assert g.ports['Y'].is_connected
    assert next(iter(g.ports['Y'].connected_wires)).raw == 'test_module1._ncgen_1_'
    assert g.ports['Y'].connected_wires == module.ports['P3'].connected_wires


def test_buffer(module: Module) -> None:
    g = factory.buffer(module)
    assert isinstance(g, lib.Buffer)
    assert g.name == '_Buffer_0_'


def test_not_gate(module: Module) -> None:
    g = factory.not_gate(module)
    assert isinstance(g, lib.NotGate)
    assert g.name == '_NotGate_0_'


def test_neg_gate(module: Module) -> None:
    g = factory.neg_gate(module)
    assert isinstance(g, lib.NegGate)
    assert g.name == '_NegGate_0_'


def test_reduce_gate(module: Module) -> None:
    with pytest.raises(WidthMismatchError):
        factory._reduce_gate(lib.ReduceOr, module, A=module.ports['P1'], Y=module.ports['P3'])
    module.create_port('P4', direction=PortDirection.IN)
    with pytest.raises(MultipleDriverError):
        factory._reduce_gate(lib.ReduceOr, module, A=module.ports['P1'], Y=module.ports['P4'])
    module._inst_gen_i = 0  # Counter gets incremented in fail cases, since they get only detected after instance creation
    module.instances.clear()

    g = factory._reduce_gate(lib.ReduceOr, module)
    assert isinstance(g, lib.ReduceOr)
    assert g.name == '_ReduceOr_0_'
    assert g.width == 1
    assert g.ports['A'].is_unconnected
    assert g.ports['Y'].is_unconnected

    module.create_port('P5', direction=PortDirection.OUT)
    g = factory._reduce_gate(lib.ReduceOr, module, A=module.ports['P1'], Y=module.ports['P5'], params={})
    assert g.name == '_ReduceOr_1_'
    assert g.width == 4
    assert g.ports['A'].is_connected
    assert g.ports['A'].width == 4
    assert next(iter(g.ports['A'].connected_wires)).raw == 'test_module1._ncgen_0_'
    assert g.ports['A'].connected_wires == module.ports['P1'].connected_wires
    assert g.ports['Y'].is_connected
    assert g.ports['Y'].width == 1
    assert next(iter(g.ports['Y'].connected_wires)).raw == 'test_module1._ncgen_1_'
    assert g.ports['Y'].connected_wires == module.ports['P5'].connected_wires


def test_reduce_and(module: Module) -> None:
    g = factory.reduce_and(module)
    assert isinstance(g, lib.ReduceAnd)
    assert g.name == '_ReduceAnd_0_'


def test_reduce_or(module: Module) -> None:
    g = factory.reduce_or(module)
    assert isinstance(g, lib.ReduceOr)
    assert g.name == '_ReduceOr_0_'


def test_reduce_bool(module: Module) -> None:
    g = factory.reduce_bool(module)
    assert isinstance(g, lib.ReduceBool)
    assert g.name == '_ReduceBool_0_'


def test_reduce_xor(module: Module) -> None:
    g = factory.reduce_xor(module)
    assert isinstance(g, lib.ReduceXor)
    assert g.name == '_ReduceXor_0_'


def test_reduce_xnor(module: Module) -> None:
    g = factory.reduce_xnor(module)
    assert isinstance(g, lib.ReduceXnor)
    assert g.name == '_ReduceXnor_0_'


def test_logic_not(module: Module) -> None:
    g = factory.logic_not(module)
    assert isinstance(g, lib.LogicNot)
    assert g.name == '_LogicNot_0_'


def test_bin_gate(module: Module) -> None:
    module.create_port('P4', direction=PortDirection.IN)
    with pytest.raises(WidthMismatchError):
        factory._bin_gate(lib._PrimitiveGate, module, A=module.ports['P1'], B=module.ports['P4'])
    module.create_port('P5', direction=PortDirection.IN, width=4)
    with pytest.raises(MultipleDriverError):
        factory._bin_gate(lib.XorGate, module, A=module.ports['P1'], Y=module.ports['P5'])

    module.instances.clear()
    g = factory._bin_gate(lib.XorGate, module)
    assert isinstance(g, lib.XorGate)
    assert g.name == '_XorGate_0_'
    assert g.width == 1
    assert g.ports['A'].is_unconnected
    assert g.ports['B'].is_unconnected
    assert g.ports['Y'].is_unconnected

    g = factory._bin_gate(lib.XorGate, module, A=module.ports['P1'], B=module.ports['P2'], Y=module.ports['P3'], params={})
    assert g.name == '_XorGate_1_'
    assert g.width == 4
    assert g.ports['A'].is_connected
    assert next(iter(g.ports['A'].connected_wires)).raw == 'test_module1._ncgen_0_'
    assert g.ports['A'].connected_wires == module.ports['P1'].connected_wires
    assert g.ports['B'].is_connected
    assert next(iter(g.ports['B'].connected_wires)).raw == 'test_module1._ncgen_1_'
    assert g.ports['B'].connected_wires == module.ports['P2'].connected_wires
    assert g.ports['Y'].is_connected
    assert next(iter(g.ports['Y'].connected_wires)).raw == 'test_module1._ncgen_2_'
    assert g.ports['Y'].connected_wires == module.ports['P3'].connected_wires


def test_and_gate(module: Module) -> None:
    g = factory.and_gate(module)
    assert isinstance(g, lib.AndGate)
    assert g.name == '_AndGate_0_'


def test_or_gate(module: Module) -> None:
    g = factory.or_gate(module)
    assert isinstance(g, lib.OrGate)
    assert g.name == '_OrGate_0_'


def test_xor_gate(module: Module) -> None:
    g = factory.xor_gate(module)
    assert isinstance(g, lib.XorGate)
    assert g.name == '_XorGate_0_'


def test_xnor_gate(module: Module) -> None:
    g = factory.xnor_gate(module)
    assert isinstance(g, lib.XnorGate)
    assert g.name == '_XnorGate_0_'


def test_nor_gate(module: Module) -> None:
    g = factory.nor_gate(module)
    assert isinstance(g, lib.NorGate)
    assert g.name == '_NorGate_0_'


def test_nand_gate(module: Module) -> None:
    g = factory.nand_gate(module)
    assert isinstance(g, lib.NandGate)
    assert g.name == '_NandGate_0_'


def test_shift_gate(module: Module) -> None:
    module.create_port('P4', direction=PortDirection.OUT)
    with pytest.raises(WidthMismatchError):
        factory._shift_gate(lib.ShiftLeft, module, A=module.ports['P1'], Y=module.ports['P4'])
    module.create_port('P5', direction=PortDirection.IN, width=4)
    with pytest.raises(MultipleDriverError):
        factory._shift_gate(lib.ShiftLeft, module, A=module.ports['P1'], Y=module.ports['P5'])

    module.instances.clear()
    module._inst_gen_i = 0
    g = factory._shift_gate(lib.ShiftLeft, module)
    assert isinstance(g, lib.ShiftLeft)
    assert g.name == '_ShiftLeft_0_'
    assert g.width == 1
    assert g.ports['A'].is_unconnected
    assert g.ports['B'].is_unconnected
    assert g.ports['Y'].is_unconnected

    warns = LOG.warns_quantity
    g2 = factory._shift_gate(lib.ShiftLeft, module, A=module.ports['P1'], B=module.ports['P2'], Y=module.ports['P3'], params={})
    assert LOG.warns_quantity == warns + 1  # Additional warning because B is wider than necessary
    assert g2.name == '_ShiftLeft_1_'

    module.disconnect(module.ports['P3'])
    module.create_port('P6', direction=PortDirection.IN, width=2)

    warns = LOG.warns_quantity
    g3 = factory._shift_gate(lib.ShiftLeft, module, A=module.ports['P1'], B=module.ports['P6'], Y=module.ports['P3'], params={})
    assert LOG.warns_quantity == warns  # No additional warning in this case
    assert g3.name == '_ShiftLeft_2_'
    assert g3.width == 4
    assert g3.ports['A'].is_connected
    assert next(iter(g3.ports['A'].connected_wires)).raw == 'test_module1._ncgen_0_'
    assert g3.ports['A'].connected_wires == module.ports['P1'].connected_wires
    assert g3.ports['B'].is_connected
    assert g3.ports['B'].width == 2
    assert g3.ports['B'].width == module.ports['P6'].width
    assert next(iter(g3.ports['B'].connected_wires)).raw == 'test_module1._ncgen_3_'  # 1 and 2 are the wires connected to g2
    assert g3.ports['B'].connected_wires == module.ports['P6'].connected_wires
    assert g3.ports['Y'].is_connected
    assert next(iter(g3.ports['Y'].connected_wires)).raw == 'test_module1._ncgen_4_'
    assert g3.ports['Y'].connected_wires == module.ports['P3'].connected_wires


def test_shift_signed(module: Module) -> None:
    g = factory.shift_signed(module)
    assert isinstance(g, lib.ShiftSigned)
    assert g.name == '_ShiftSigned_0_'


def test_shift_left(module: Module) -> None:
    g = factory.shift_left(module)
    assert isinstance(g, lib.ShiftLeft)
    assert g.name == '_ShiftLeft_0_'


def test_shift_right(module: Module) -> None:
    g = factory.shift_right(module)
    assert isinstance(g, lib.ShiftRight)
    assert g.name == '_ShiftRight_0_'


def test_binNto1_gate(module: Module) -> None:
    with pytest.raises(WidthMismatchError):
        factory._binNto1_gate(lib.LogicAnd, module, A=module.ports['P1'], Y=module.ports['P3'])
    module.create_port('P4', direction=PortDirection.IN)
    with pytest.raises(MultipleDriverError):
        factory._binNto1_gate(lib.LogicAnd, module, A=module.ports['P1'], Y=module.ports['P4'])
    module._inst_gen_i = 0  # Counter gets incremented in fail cases, since they get only detected after instance creation
    module.instances.clear()

    g = factory._binNto1_gate(lib.LogicAnd, module)
    assert isinstance(g, lib.LogicAnd)
    assert g.name == '_LogicAnd_0_'
    assert g.width == 1
    assert g.ports['A'].is_unconnected
    assert g.ports['B'].is_unconnected
    assert g.ports['Y'].is_unconnected

    module.create_port('P5', direction=PortDirection.OUT)
    g = factory._binNto1_gate(lib.LogicAnd, module, A=module.ports['P1'], B=module.ports['P2'], Y=module.ports['P5'], params={})
    assert g.name == '_LogicAnd_1_'
    assert g.width == 4
    assert g.ports['A'].is_connected
    assert g.ports['A'].width == 4
    assert next(iter(g.ports['A'].connected_wires)).raw == 'test_module1._ncgen_0_'
    assert g.ports['A'].connected_wires == module.ports['P1'].connected_wires
    assert g.ports['B'].is_connected
    assert g.ports['B'].width == 4
    assert next(iter(g.ports['B'].connected_wires)).raw == 'test_module1._ncgen_1_'
    assert g.ports['B'].connected_wires == module.ports['P2'].connected_wires
    assert g.ports['Y'].is_connected
    assert g.ports['Y'].width == 1
    assert next(iter(g.ports['Y'].connected_wires)).raw == 'test_module1._ncgen_2_'
    assert g.ports['Y'].connected_wires == module.ports['P5'].connected_wires


def test_logic_and(module: Module) -> None:
    g = factory.logic_and(module)
    assert isinstance(g, lib.LogicAnd)
    assert g.name == '_LogicAnd_0_'


def test_logic_or(module: Module) -> None:
    g = factory.logic_or(module)
    assert isinstance(g, lib.LogicOr)
    assert g.name == '_LogicOr_0_'


def test_less_than(module: Module) -> None:
    g = factory.less_than(module)
    assert isinstance(g, lib.LessThan)
    assert g.name == '_LessThan_0_'


def test_less_equal(module: Module) -> None:
    g = factory.less_equal(module)
    assert isinstance(g, lib.LessEqual)
    assert g.name == '_LessEqual_0_'


def test_equal(module: Module) -> None:
    g = factory.equal(module)
    assert isinstance(g, lib.Equal)
    assert g.name == '_Equal_0_'


def test_not_equal(module: Module) -> None:
    g = factory.not_equal(module)
    assert isinstance(g, lib.NotEqual)
    assert g.name == '_NotEqual_0_'


def test_greater_than(module: Module) -> None:
    g = factory.greater_than(module)
    assert isinstance(g, lib.GreaterThan)
    assert g.name == '_GreaterThan_0_'


def test_greater_equal(module: Module) -> None:
    g = factory.greater_equal(module)
    assert isinstance(g, lib.GreaterEqual)
    assert g.name == '_GreaterEqual_0_'


def test_multiplexer(module: Module) -> None:
    module.create_port('P4', direction=PortDirection.OUT)
    D0 = module.create_port('D0', direction=PortDirection.IN, width=4)
    D1 = module.create_port('D1', direction=PortDirection.IN, width=4)
    D2 = module.create_port('D2', direction=PortDirection.IN, width=4)
    D3 = module.create_port('D3', direction=PortDirection.IN, width=4)
    Ds = [D0, D1, D2, D3]
    with pytest.raises(WidthMismatchError):
        factory.multiplexer(module, D_ports=Ds, Y=module.ports['P4'])
    with pytest.raises(WidthMismatchError):
        # S.width == 1 != log2(4) == 2 !!!
        factory.multiplexer(module, D_ports=Ds, S=module.ports['P2'], Y=module.ports['P3'])
    module.create_port('P5', direction=PortDirection.IN, width=4)
    with pytest.raises(MultipleDriverError):
        factory.multiplexer(module, D_ports=Ds, Y=module.ports['P5'])

    module.instances.clear()
    g = factory.multiplexer(module)
    assert isinstance(g, lib.Multiplexer)
    assert g.name == '_Multiplexer_0_'
    assert g.width == 1
    assert len(g.ports) == 4
    assert g.ports['D_0'].is_unconnected
    assert g.ports['D_1'].is_unconnected
    assert g.ports['S'].is_unconnected
    assert g.ports['Y'].is_unconnected

    module.create_port('P6', direction=PortDirection.IN, width=2)
    g = factory.multiplexer(module, D_ports=Ds, S=module.ports['P6'], Y=module.ports['P3'], params={})
    assert g.name == '_Multiplexer_1_'
    assert g.width == 4
    assert g.bit_width == 2
    assert g.ports['D_0'].is_connected
    assert g.ports['D_0'].width == 4
    assert next(iter(g.ports['D_0'].connected_wires)).raw == 'test_module1._ncgen_0_'
    assert g.ports['D_0'].connected_wires == module.ports['D0'].connected_wires
    assert g.ports['D_1'].is_connected
    assert g.ports['D_1'].width == 4
    assert next(iter(g.ports['D_1'].connected_wires)).raw == 'test_module1._ncgen_1_'
    assert g.ports['D_1'].connected_wires == module.ports['D1'].connected_wires
    assert g.ports['D_2'].is_connected
    assert g.ports['D_2'].width == 4
    assert next(iter(g.ports['D_2'].connected_wires)).raw == 'test_module1._ncgen_2_'
    assert g.ports['D_2'].connected_wires == module.ports['D2'].connected_wires
    assert g.ports['D_3'].is_connected
    assert g.ports['D_3'].width == 4
    assert next(iter(g.ports['D_3'].connected_wires)).raw == 'test_module1._ncgen_3_'
    assert g.ports['D_3'].connected_wires == module.ports['D3'].connected_wires
    assert g.ports['S'].is_connected
    assert g.ports['S'].width == 2
    assert next(iter(g.ports['S'].connected_wires)).raw == 'test_module1._ncgen_4_'
    assert g.ports['S'].connected_wires == module.ports['P6'].connected_wires
    assert g.ports['Y'].is_connected
    assert g.ports['Y'].width == 4
    assert next(iter(g.ports['Y'].connected_wires)).raw == 'test_module1._ncgen_5_'
    assert g.ports['Y'].connected_wires == module.ports['P3'].connected_wires


def test_demultiplexer(module: Module) -> None:
    module.create_port('P4', direction=PortDirection.OUT)
    Y0 = module.create_port('Y0', direction=PortDirection.OUT, width=4)
    Y1 = module.create_port('Y1', direction=PortDirection.OUT, width=4)
    Y2 = module.create_port('Y2', direction=PortDirection.OUT, width=4)
    Y3 = module.create_port('Y3', direction=PortDirection.OUT, width=4)
    Ys = [Y0, Y1, Y2, Y3]
    with pytest.raises(WidthMismatchError):
        factory.demultiplexer(module, D=module.ports['P4'], Y_ports=Ys)
    with pytest.raises(WidthMismatchError):
        # S.width == 1 != log2(4) == 2 !!!
        factory.demultiplexer(module, D=module.ports['P1'], S=module.ports['P2'], Y_ports=Ys)
    module.create_port('P6', direction=PortDirection.IN, width=2)
    with pytest.raises(MultipleDriverError):
        # Correct S.width ( == 2), but one of the outputs would cause driver conflicts
        Y3.direction = PortDirection.IN
        factory.demultiplexer(module, D=module.ports['P1'], S=module.ports['P6'], Y_ports=Ys)
    Y3.direction = PortDirection.OUT
    for p in [module.ports['P6'], *Ys]:
        module.disconnect(p)

    module.instances.clear()
    module.wires.clear()
    module._wire_gen_i = 0
    g = factory.demultiplexer(module)
    assert isinstance(g, lib.Demultiplexer)
    assert g.name == '_Demultiplexer_0_'
    assert g.width == 1
    assert len(g.ports) == 4
    assert g.ports['D'].is_unconnected
    assert g.ports['S'].is_unconnected
    assert g.ports['Y_0'].is_unconnected
    assert g.ports['Y_1'].is_unconnected

    g = factory.demultiplexer(module, D=module.ports['P3'], S=module.ports['P6'], Y_ports=Ys, params={})
    assert g.name == '_Demultiplexer_1_'
    assert g.width == 4
    assert g.bit_width == 2
    assert g.ports['D'].is_connected
    assert g.ports['D'].width == 4
    assert next(iter(g.ports['D'].connected_wires)).raw == 'test_module1._ncgen_0_'
    assert g.ports['D'].connected_wires == module.ports['P3'].connected_wires
    assert g.ports['S'].is_connected
    assert g.ports['S'].width == 2
    assert next(iter(g.ports['S'].connected_wires)).raw == 'test_module1._ncgen_1_'
    assert g.ports['S'].connected_wires == module.ports['P6'].connected_wires
    assert g.ports['Y_0'].is_connected
    assert g.ports['Y_0'].width == 4
    assert next(iter(g.ports['Y_0'].connected_wires)).raw == 'test_module1._ncgen_2_'
    assert g.ports['Y_0'].connected_wires == module.ports['Y0'].connected_wires
    assert g.ports['Y_1'].is_connected
    assert g.ports['Y_1'].width == 4
    assert next(iter(g.ports['Y_1'].connected_wires)).raw == 'test_module1._ncgen_3_'
    assert g.ports['Y_1'].connected_wires == module.ports['Y1'].connected_wires
    assert g.ports['Y_2'].is_connected
    assert g.ports['Y_2'].width == 4
    assert next(iter(g.ports['Y_2'].connected_wires)).raw == 'test_module1._ncgen_4_'
    assert g.ports['Y_2'].connected_wires == module.ports['Y2'].connected_wires
    assert g.ports['Y_3'].is_connected
    assert g.ports['Y_3'].width == 4
    assert next(iter(g.ports['Y_3'].connected_wires)).raw == 'test_module1._ncgen_5_'
    assert g.ports['Y_3'].connected_wires == module.ports['Y3'].connected_wires


def test_dff_gate(module: Module) -> None:
    module.create_port('P4', direction=PortDirection.OUT)
    with pytest.raises(WidthMismatchError):
        factory.dff(module, D=module.ports['P1'], Q=module.ports['P4'])
    with pytest.raises(WidthMismatchError):
        factory.dff(module, RST=module.ports['P1'])
    module.create_port('P5', direction=PortDirection.IN, width=4)
    with pytest.raises(MultipleDriverError):
        factory.dff(module, D=module.ports['P1'], Q=module.ports['P5'], params={})

    module.instances.clear()
    module._inst_gen_i = 0
    g = factory.dff(module)
    assert isinstance(g, lib.DFF)
    assert g.name == '_DFF_0_'
    assert g.width == 1
    assert g.ports['D'].is_unconnected
    assert g.ports['CLK'].is_unconnected
    assert g.ports['RST'].is_unconnected
    assert g.ports['EN'].is_unconnected
    assert g.ports['Q'].is_unconnected

    module.create_port('P6', direction=PortDirection.IN)
    module.create_port('P7', direction=PortDirection.IN)
    g = factory.dff(
        module, D=module.ports['P1'], CLK=module.ports['P6'], RST=module.ports['P7'], EN=module.ports['P6'], Q=module.ports['P3'], params={}
    )
    assert g.name == '_DFF_1_'
    assert g.width == 4
    assert g.ports['D'].is_connected
    assert g.ports['D'].width == 4
    assert next(iter(g.ports['D'].connected_wires)).raw == 'test_module1._ncgen_0_'
    assert g.ports['D'].connected_wires == module.ports['P1'].connected_wires
    assert g.ports['CLK'].is_connected
    assert g.ports['CLK'].width == 1
    assert next(iter(g.ports['CLK'].connected_wires)).raw == 'test_module1._ncgen_1_'
    assert g.ports['CLK'].connected_wires == module.ports['P6'].connected_wires
    assert g.ports['RST'].is_connected
    assert g.ports['RST'].width == 1
    assert next(iter(g.ports['RST'].connected_wires)).raw == 'test_module1._ncgen_2_'
    assert g.ports['RST'].connected_wires == module.ports['P7'].connected_wires
    assert g.ports['EN'].is_connected
    assert g.ports['EN'].width == 1
    assert next(iter(g.ports['EN'].connected_wires)).raw == 'test_module1._ncgen_1_'
    assert g.ports['EN'].connected_wires == module.ports['P6'].connected_wires
    assert g.ports['Q'].is_connected
    assert g.ports['Q'].width == 4
    assert next(iter(g.ports['Q'].connected_wires)).raw == 'test_module1._ncgen_3_'
    assert g.ports['Q'].connected_wires == module.ports['P3'].connected_wires


def test_dlatch_gate(module: Module) -> None:
    module.create_port('P4', direction=PortDirection.OUT)
    with pytest.raises(WidthMismatchError):
        factory.dlatch(module, D=module.ports['P1'], Q=module.ports['P4'])
    with pytest.raises(WidthMismatchError):
        factory.dlatch(module, EN=module.ports['P1'])
    module.create_port('P5', direction=PortDirection.IN, width=4)
    with pytest.raises(MultipleDriverError):
        factory.dlatch(module, D=module.ports['P1'], Q=module.ports['P5'], params={})

    module.instances.clear()
    module._inst_gen_i = 0
    g = factory.dlatch(module)
    assert isinstance(g, lib.DLatch)
    assert g.name == '_DLatch_0_'
    assert g.width == 1
    assert g.ports['D'].is_unconnected
    assert g.ports['EN'].is_unconnected
    assert g.ports['Q'].is_unconnected

    module.create_port('P6', direction=PortDirection.IN)
    g = factory.dlatch(module, D=module.ports['P1'], EN=module.ports['P6'], Q=module.ports['P3'], params={})
    assert g.name == '_DLatch_1_'
    assert g.width == 4
    assert g.ports['D'].is_connected
    assert g.ports['D'].width == 4
    assert next(iter(g.ports['D'].connected_wires)).raw == 'test_module1._ncgen_0_'
    assert g.ports['D'].connected_wires == module.ports['P1'].connected_wires
    assert g.ports['EN'].is_connected
    assert g.ports['EN'].width == 1
    assert next(iter(g.ports['EN'].connected_wires)).raw == 'test_module1._ncgen_1_'
    assert g.ports['EN'].connected_wires == module.ports['P6'].connected_wires
    assert g.ports['Q'].is_connected
    assert g.ports['Q'].width == 4
    assert next(iter(g.ports['Q'].connected_wires)).raw == 'test_module1._ncgen_2_'
    assert g.ports['Q'].connected_wires == module.ports['P3'].connected_wires


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
