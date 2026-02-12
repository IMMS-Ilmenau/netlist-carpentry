import json
import math
import os
import types
from typing import ClassVar

import pytest

import netlist_carpentry.routines.floodfill.chain_optimizer as co
from netlist_carpentry import Module, ModuleGraph
from netlist_carpentry.core.enums.direction import Direction as Dir
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.utils.gate_lib import AndGate, OrGate, XorGate


@pytest.fixture()
def empty_module() -> Module:
    return Module(raw_path='test_module')


@pytest.fixture()
def module_with_or_chain() -> Module:
    m = Module(raw_path='or_chain_module')

    p_in1 = m.create_port('in1_port', Dir.IN)
    p_in2 = m.create_port('in2_port', Dir.IN)
    p_in3 = m.create_port('in3_port', Dir.IN)
    p_in4 = m.create_port('in4_port', Dir.IN)

    w_in1 = m.create_wire('in1')
    w_in2 = m.create_wire('in2')
    w_in3 = m.create_wire('in3')
    w_in4 = m.create_wire('in4')

    m.connect(w_in1[0], p_in1[0])
    m.connect(w_in2[0], p_in2[0])
    m.connect(w_in3[0], p_in3[0])
    m.connect(w_in4[0], p_in4[0])

    w_or1_out = m.create_wire('or1_out')
    w_or2_out = m.create_wire('or2_out')

    w_out = m.create_wire('out')
    p_out = m.create_port('out_port', Dir.OUT)
    m.connect(w_out[0], p_out[0])

    or1 = m.create_instance(OrGate, 'or1')
    or2 = m.create_instance(OrGate, 'or2')
    or3 = m.create_instance(OrGate, 'or3')

    m.connect(w_in1[0], or1.ports['A'][0])
    m.connect(w_in2[0], or1.ports['B'][0])
    m.connect(w_or1_out[0], or1.ports['Y'][0])

    m.connect(w_or1_out[0], or2.ports['A'][0])
    m.connect(w_in3[0], or2.ports['B'][0])
    m.connect(w_or2_out[0], or2.ports['Y'][0])

    m.connect(w_or2_out[0], or3.ports['A'][0])
    m.connect(w_in4[0], or3.ports['B'][0])
    m.connect(w_out[0], or3.ports['Y'][0])

    return m


@pytest.fixture()
def module_with_and_chain() -> Module:
    m = Module(raw_path='and_chain_module')

    p_in1 = m.create_port('in1_port', Dir.IN)
    p_in2 = m.create_port('in2_port', Dir.IN)
    p_in3 = m.create_port('in3_port', Dir.IN)
    p_in4 = m.create_port('in4_port', Dir.IN)

    w_in1 = m.create_wire('in1')
    w_in2 = m.create_wire('in2')
    w_in3 = m.create_wire('in3')
    w_in4 = m.create_wire('in4')

    m.connect(w_in1[0], p_in1[0])
    m.connect(w_in2[0], p_in2[0])
    m.connect(w_in3[0], p_in3[0])
    m.connect(w_in4[0], p_in4[0])

    w_and1_out = m.create_wire('and1_out')
    w_and2_out = m.create_wire('and2_out')

    w_out = m.create_wire('out')
    p_out = m.create_port('out_port', Dir.OUT)
    m.connect(w_out[0], p_out[0])

    and1 = m.create_instance(AndGate, 'and1')
    and2 = m.create_instance(AndGate, 'and2')
    and3 = m.create_instance(AndGate, 'and3')

    m.connect(w_in1[0], and1.ports['A'][0])
    m.connect(w_in2[0], and1.ports['B'][0])
    m.connect(w_and1_out[0], and1.ports['Y'][0])

    m.connect(w_and1_out[0], and2.ports['A'][0])
    m.connect(w_in3[0], and2.ports['B'][0])
    m.connect(w_and2_out[0], and2.ports['Y'][0])

    m.connect(w_and2_out[0], and3.ports['A'][0])
    m.connect(w_in4[0], and3.ports['B'][0])
    m.connect(w_out[0], and3.ports['Y'][0])

    return m


@pytest.fixture()
def module_with_two_chains() -> Module:
    m = Module(raw_path='two_chains_module')

    # Chain 1
    p_in1 = m.create_port('in1_port', Dir.IN)
    p_in2 = m.create_port('in2_port', Dir.IN)
    p_in3 = m.create_port('in3_port', Dir.IN)

    w_in1 = m.create_wire('in1')
    w_in2 = m.create_wire('in2')
    w_in3 = m.create_wire('in3')
    w_chain1_mid = m.create_wire('chain1_mid')
    w_chain1_out = m.create_wire('chain1_out')

    m.connect(w_in1[0], p_in1[0])
    m.connect(w_in2[0], p_in2[0])
    m.connect(w_in3[0], p_in3[0])

    p_chain1_out = m.create_port('chain1_out_port', Dir.OUT)
    m.connect(w_chain1_out[0], p_chain1_out[0])

    or1a = m.create_instance(OrGate, 'or1a')
    or1b = m.create_instance(OrGate, 'or1b')

    m.connect(w_in1[0], or1a.ports['A'][0])
    m.connect(w_in2[0], or1a.ports['B'][0])
    m.connect(w_chain1_mid[0], or1a.ports['Y'][0])

    m.connect(w_chain1_mid[0], or1b.ports['A'][0])
    m.connect(w_in3[0], or1b.ports['B'][0])
    m.connect(w_chain1_out[0], or1b.ports['Y'][0])

    # Chain 2
    p_in4 = m.create_port('in4_port', Dir.IN)
    p_in5 = m.create_port('in5_port', Dir.IN)
    p_in6 = m.create_port('in6_port', Dir.IN)

    w_in4 = m.create_wire('in4')
    w_in5 = m.create_wire('in5')
    w_in6 = m.create_wire('in6')
    w_chain2_mid = m.create_wire('chain2_mid')
    w_chain2_out = m.create_wire('chain2_out')

    m.connect(w_in4[0], p_in4[0])
    m.connect(w_in5[0], p_in5[0])
    m.connect(w_in6[0], p_in6[0])

    p_chain2_out = m.create_port('chain2_out_port', Dir.OUT)
    m.connect(w_chain2_out[0], p_chain2_out[0])

    or2a = m.create_instance(OrGate, 'or2a')
    or2b = m.create_instance(OrGate, 'or2b')

    m.connect(w_in4[0], or2a.ports['A'][0])
    m.connect(w_in5[0], or2a.ports['B'][0])
    m.connect(w_chain2_mid[0], or2a.ports['Y'][0])

    m.connect(w_chain2_mid[0], or2b.ports['A'][0])
    m.connect(w_in6[0], or2b.ports['B'][0])
    m.connect(w_chain2_out[0], or2b.ports['Y'][0])

    return m


@pytest.fixture()
def module_with_mixed_gates() -> Module:
    m = Module(raw_path='mixed_module')

    p_in1 = m.create_port('in1_port', Dir.IN)
    p_in2 = m.create_port('in2_port', Dir.IN)
    p_in3 = m.create_port('in3_port', Dir.IN)

    w_in1 = m.create_wire('in1')
    w_in2 = m.create_wire('in2')
    w_in3 = m.create_wire('in3')
    w_and_out = m.create_wire('and_out')
    w_or_out = m.create_wire('or_out')
    w_out = m.create_wire('out')

    m.connect(w_in1[0], p_in1[0])
    m.connect(w_in2[0], p_in2[0])
    m.connect(w_in3[0], p_in3[0])

    p_out = m.create_port('out_port', Dir.OUT)
    m.connect(w_out[0], p_out[0])

    and_gate = m.create_instance(AndGate, 'and1')
    or_gate = m.create_instance(OrGate, 'or1')
    xor_gate = m.create_instance(XorGate, 'xor1')

    m.connect(w_in1[0], and_gate.ports['A'][0])
    m.connect(w_in2[0], and_gate.ports['B'][0])
    m.connect(w_and_out[0], and_gate.ports['Y'][0])

    m.connect(w_and_out[0], or_gate.ports['A'][0])
    m.connect(w_in3[0], or_gate.ports['B'][0])
    m.connect(w_or_out[0], or_gate.ports['Y'][0])

    m.connect(w_or_out[0], xor_gate.ports['A'][0])
    m.connect(w_in1[0], xor_gate.ports['B'][0])
    m.connect(w_out[0], xor_gate.ports['Y'][0])

    return m


@pytest.fixture()
def or_config():
    return co.get_gate_config('or')


@pytest.fixture()
def and_config():
    return co.get_gate_config('and')


@pytest.fixture()
def boundary_extractor():
    return co.ChainBoundaryExtractor()


@pytest.fixture()
def chain_replacer(boundary_extractor):
    return co.ChainReplacer(boundary_extractor=boundary_extractor)


@pytest.fixture()
def scanner():
    return co.GateChainScanner(script_path=co.__file__)


@pytest.fixture()
def simple_graph_with_or_chain() -> ModuleGraph:
    g = ModuleGraph()
    g.add_node('module.or1', ntype='INSTANCE', nsubtype='§or', raw_path='module.or1')
    g.add_node('module.or2', ntype='INSTANCE', nsubtype='§or', raw_path='module.or2')
    g.add_node('module.or3', ntype='INSTANCE', nsubtype='§or', raw_path='module.or3')
    g.add_node('module.and1', ntype='INSTANCE', nsubtype='§and', raw_path='module.and1')
    g.add_node('in1', ntype='PORT', nsubtype='input')
    g.add_node('out', ntype='PORT', nsubtype='output')

    g.add_edge('module.and1', 'module.or1')
    g.add_edge('in1', 'module.or1')
    g.add_edge('module.or1', 'module.or2')
    g.add_edge('in1', 'module.or2')
    g.add_edge('module.or2', 'module.or3')
    g.add_edge('in1', 'module.or3')
    g.add_edge('module.or3', 'out')
    return g


def test_get_gate_config_ok_invalid_empty():
    cfg = co.get_gate_config('§Or')
    assert cfg.name == 'or'
    assert cfg.nsubtype == '§or'
    assert cfg.chain_prefix == 'or_chain'
    assert cfg.gate_cls is OrGate

    with pytest.raises(ValueError, match='Unsupported gate'):
        co.get_gate_config('invalid_gate_zzz')

    with pytest.raises(ValueError, match='must not be empty'):
        co.get_gate_config('')


def test_get_gate_config_and_xor():
    and_cfg = co.get_gate_config('and')
    assert and_cfg.name == 'and'
    assert and_cfg.gate_cls is AndGate

    xor_cfg = co.get_gate_config('xor')
    assert xor_cfg.name == 'xor'
    assert xor_cfg.gate_cls is XorGate


def test_is_gate_subtype_mismatch_and_nsubtype(or_config):
    g = ModuleGraph()
    g.add_node('m.or1', ntype='INSTANCE', nsubtype='§and')
    assert co.is_gate(g, 'm.or1', or_config) is False

    g2 = ModuleGraph()
    g2.add_node('m.or2', ntype='INSTANCE', nsubtype='§or')
    assert co.is_gate(g2, 'm.or2', or_config) is True


def test_is_gate_not_instance(or_config):
    g = ModuleGraph()
    g.add_node('m.port', ntype='PORT', nsubtype='§or')
    assert co.is_gate(g, 'm.port', or_config) is False


def test_is_gate_exclude_chains_flag(or_config):
    g = ModuleGraph()
    g.add_node('m.or_chain1_L0_N0', ntype='INSTANCE', nsubtype='§or')
    assert co.is_gate(g, 'm.or_chain1_L0_N0', or_config, exclude_chains=True) is False
    assert co.is_gate(g, 'm.or_chain1_L0_N0', or_config, exclude_chains=False) is True


def test_is_chain_head_node_not_in_gate_nodes(simple_graph_with_or_chain):
    assert co.is_chain_head(simple_graph_with_or_chain, 'module.or1', set()) is False


def test_is_chain_head_has_gate_predecessor(simple_graph_with_or_chain):
    g = simple_graph_with_or_chain
    gate_nodes = {'module.or1', 'module.or2', 'module.or3'}
    assert co.is_chain_head(g, 'module.or2', gate_nodes) is False


def test_build_chain_and_find_gate_chains(simple_graph_with_or_chain, or_config):
    g = simple_graph_with_or_chain
    gate_nodes = {n for n in g.nodes if co.is_gate(g, n, or_config)}
    chain = co.build_chain(g, 'module.or1', gate_nodes)
    assert chain == ['module.or1', 'module.or2', 'module.or3']

    chains = co.find_gate_chains(g, or_config)
    assert chains == [chain]


def test_build_chain_stops_at_multiple_successors(or_config):
    g = ModuleGraph()
    g.add_node('m.or1', ntype='INSTANCE', nsubtype='§or')
    g.add_node('m.or2', ntype='INSTANCE', nsubtype='§or')
    g.add_node('m.or3', ntype='INSTANCE', nsubtype='§or')
    g.add_edge('m.or1', 'm.or2')
    g.add_edge('m.or1', 'm.or3')

    gate_nodes = {'m.or1', 'm.or2', 'm.or3'}
    chain = co.build_chain(g, 'm.or1', gate_nodes)
    assert chain == ['m.or1']


def test_find_gate_chains_single_gate_no_chain(or_config):
    g = ModuleGraph()
    g.add_node('m.or1', ntype='INSTANCE', nsubtype='§or')
    assert co.find_gate_chains(g, or_config) == []


def test_find_gate_chains_visited_nodes_skipped(or_config):
    g = ModuleGraph()
    g.add_node('m.or1', ntype='INSTANCE', nsubtype='§or')
    g.add_node('m.or2', ntype='INSTANCE', nsubtype='§or')
    g.add_edge('m.or1', 'm.or2')

    chains = co.find_gate_chains(g, or_config)
    assert len(chains) == 1


def test_extract_instance_key_priority_and_fallback():
    g = ModuleGraph()
    g.add_node('n1', raw_path='raw', path='path', name='name')
    assert co.extract_instance_key(g, 'n1') == 'raw'

    g2 = ModuleGraph()
    g2.add_node('n2', raw_path='')
    assert co.extract_instance_key(g2, 'n2') == 'n2'

    g3 = ModuleGraph()
    g3.add_node('n3', path='pathval')
    assert co.extract_instance_key(g3, 'n3') == 'pathval'


@pytest.mark.parametrize(
    'raw, expected',
    [
        ('module.w.0', True),
        ('0', False),
        ('', False),
    ],
)
def test_is_valid_wire_path(raw, expected):
    class MW:
        pass

    mw = MW()
    mw.raw = raw
    assert co.is_valid_wire_path(mw) is expected
    assert co.is_valid_wire_path(None) is False


@pytest.mark.parametrize(
    'raw, expected',
    [
        ('0', True),
        ('1', True),
        ('x', True),
        ('z', True),
        ('X', True),
        ('Z', True),
        ("1'b0", True),
        ("1'B1", True),
        ("1'bx", True),
        ("1'bz", True),
        ('module.w.0', False),
        ('', True),
    ],
)
def test_is_constant_wire(raw, expected):
    class MW:
        pass

    mw = MW()
    mw.raw = raw
    assert co.is_constant_wire(mw) is expected
    assert co.is_constant_wire(None) is True


def test_safe_get_driver_and_wire_path_exception_paths():
    class BadSeg1:
        def driver(self):
            raise AttributeError('no driver')

    assert co.safe_get_driver(BadSeg1()) is None

    class BadSeg2:
        @property
        def ws_path(self):
            raise AttributeError('no ws_path')

    assert co.safe_get_wire_path(BadSeg2()) is None


def test_safe_get_driver_returns_value():
    class GoodSeg:
        def driver(self):
            return 'driver_obj'

    assert co.safe_get_driver(GoodSeg()) == 'driver_obj'


def test_safe_get_wire_path_returns_value():
    ws = WireSegmentPath(raw='m.w.0')

    class GoodSeg:
        @property
        def ws_path(self):
            return ws

    assert co.safe_get_wire_path(GoodSeg()) == ws


def test_is_target_gate_exclude_chains_block(empty_module, or_config):
    chain_gate = empty_module.create_instance(OrGate, 'or_chain99_L0_N0')
    assert co.is_target_gate(chain_gate, or_config, exclude_chains=True) is False
    assert co.is_target_gate(chain_gate, or_config, exclude_chains=False) is True


def test_is_target_gate_raw_path_empty_ok(or_config):
    class DummyInst:
        instance_type = '§or'
        raw_path = ''

    assert co.is_target_gate(DummyInst(), or_config, exclude_chains=True) is True


def test_is_target_gate_wrong_type(or_config):
    class DummyInst:
        instance_type = '§and'
        raw_path = 'm.and1'

    assert co.is_target_gate(DummyInst(), or_config) is False


def test_build_gate_connectivity_handles_missing_ports(or_config):
    class Seg:
        def __init__(self, raw=None):
            self._raw = raw

        @property
        def ws_path(self):
            return None if self._raw is None else WireSegmentPath(raw=self._raw)

    class Inst:
        def __init__(self, raw_path, ports):
            self.raw_path = raw_path
            self.instance_type = '§or'
            self.ports = ports

    class DummyModule:
        def __init__(self, instances):
            self.instances = instances

    i1 = Inst('m.or1', ports={'A': [(0, Seg('m.a.0'))], 'B': [(0, Seg('m.b.0'))]})
    i2 = Inst('m.or2', ports={'Y': [(0, Seg(None))], 'A': [(0, Seg('m.x.0'))]})
    i3 = Inst('m.or3', ports={'Y': [(0, Seg('m.y.0'))], 'A': [(0, Seg('m.x.0'))]})

    m = DummyModule({'or1': i1, 'or2': i2, 'or3': i3})
    gates, preds, succs = co.build_gate_connectivity(m, or_config)
    assert len(gates) == 3
    assert set(preds.keys()) == set(gates.keys())
    assert set(succs.keys()) == set(gates.keys())


def test_build_gate_connectivity_empty_module(empty_module, or_config):
    gates, preds, succs = co.build_gate_connectivity(empty_module, or_config)
    assert gates == {}
    assert preds == {}
    assert succs == {}


def test_build_gate_connectivity_with_connections(module_with_or_chain, or_config):
    module_with_or_chain.optimize()
    gates, preds, _ = co.build_gate_connectivity(module_with_or_chain, or_config)
    assert len(gates) == 3
    heads = [p for p, pred_set in preds.items() if len(pred_set) == 0]
    assert len(heads) == 1


def test_find_gate_chains_netlist_or_chain(module_with_or_chain, or_config):
    module_with_or_chain.optimize()
    chains = co.find_gate_chains_netlist(module_with_or_chain, or_config)
    assert len(chains) == 1
    assert len(chains[0]) == 3


def test_find_gate_chains_netlist_two_chains(module_with_two_chains, or_config):
    module_with_two_chains.optimize()
    chains = co.find_gate_chains_netlist(module_with_two_chains, or_config)
    assert len(chains) == 2
    assert sorted(len(c) for c in chains) == [2, 2]


def test_find_gate_chains_netlist_empty_module(empty_module, or_config):
    assert co.find_gate_chains_netlist(empty_module, or_config) == []


def test_find_gate_chains_netlist_no_chains_single_gates(module_with_mixed_gates, or_config):
    module_with_mixed_gates.optimize()
    chains = co.find_gate_chains_netlist(module_with_mixed_gates, or_config)
    assert len(chains) == 0


def test_extract_boundary_empty_raises(boundary_extractor):
    with pytest.raises(ValueError, match='Empty chain'):
        boundary_extractor.extract_boundary([])


def test_collect_output_wires_and_external_inputs(module_with_or_chain, boundary_extractor):
    module_with_or_chain.optimize()
    insts = [
        module_with_or_chain.instances['or1'],
        module_with_or_chain.instances['or2'],
        module_with_or_chain.instances['or3'],
    ]

    out, internal = boundary_extractor.collect_output_wires(insts)
    assert out is not None
    assert len(internal) == 2

    chain_ids = {i.raw_path for i in insts}
    inputs, consts = boundary_extractor.collect_external_inputs(insts, chain_ids)
    assert len(inputs) == 4
    assert consts == 0


def test_collect_output_wires_missing_port_y_raises(boundary_extractor):
    class MockInstance:
        raw_path = 'test.mock'
        ports: ClassVar[dict[str, list[tuple[int]]]] = {}

    with pytest.raises(RuntimeError, match='missing port Y'):
        boundary_extractor.collect_output_wires([MockInstance()])


def test_collect_output_wires_multiple_segments_raises(boundary_extractor):
    class Seg:
        def __init__(self, raw):
            self.ws_path = WireSegmentPath(raw=raw)

    class Inst:
        raw_path = 'm.i'
        ports: ClassVar[dict[str, list[tuple[int, Seg]]]] = {'Y': [(0, Seg('m.w1.0')), (1, Seg('m.w2.0'))]}

    with pytest.raises(RuntimeError, match='expected 1 output segment'):
        boundary_extractor.collect_output_wires([Inst()])


def test_collect_output_wires_invalid_output_raises(boundary_extractor):
    class Seg:
        def __init__(self, raw):
            self.ws_path = WireSegmentPath(raw=raw)

    class Inst:
        raw_path = 'm.i'

        def __init__(self) -> None:
            self.ports = {'Y': [(0, Seg('0'))]}

    with pytest.raises(RuntimeError, match='invalid output wire'):
        boundary_extractor.collect_output_wires([Inst()])


def test_collect_external_inputs_branches(boundary_extractor):
    class DriverOK:
        def __init__(self, parent_raw_path):
            self.port = types.SimpleNamespace(parent=types.SimpleNamespace(raw_path=parent_raw_path))

    class DriverBad:
        pass

    class Seg:
        def __init__(self, raw, driver=None):
            self.ws_path = WireSegmentPath(raw=raw)
            self._driver = driver

        def driver(self):
            return self._driver

    class Inst:
        def __init__(self, raw_path, ports):
            self.raw_path = raw_path
            self.ports = ports

    chain_ids = {'m.g1'}

    inst = Inst(
        'm.g2',
        ports={
            'B': [
                (0, Seg('0')),
                (1, Seg('m.ext.0', driver=None)),
                (2, Seg('m.int.0', driver=DriverOK('m.g1'))),
                (3, Seg('m.ext2.0', driver=DriverBad())),
            ]
        },
    )

    inputs, consts = boundary_extractor.collect_external_inputs([inst], chain_ids, internal_wire_paths=set())
    raws = sorted([w.raw for w in inputs])

    assert consts == 1
    assert raws == ['m.ext.0', 'm.ext2.0']


def test_collect_external_inputs_filters_internal_wires(boundary_extractor):
    class Seg:
        def __init__(self, raw):
            self.ws_path = WireSegmentPath(raw=raw)

        def driver(self):
            return None

    class Inst:
        def __init__(self, raw_path, ports):
            self.raw_path = raw_path
            self.ports = ports

    inst = Inst(
        'm.g1',
        ports={
            'A': [(0, Seg('m.internal.0'))],
            'B': [(0, Seg('m.external.0'))],
        },
    )

    inputs, _consts = boundary_extractor.collect_external_inputs(
        [inst],
        chain_ids=set(),
        internal_wire_paths={'m.internal.0'},
    )
    assert len(inputs) == 1
    assert inputs[0].raw == 'm.external.0'


def test_extract_boundary_degenerate_constants_like(boundary_extractor):
    class Seg:
        def __init__(self, raw):
            self.ws_path = WireSegmentPath(raw=raw)

        def driver(self):
            return None

    class Inst:
        def __init__(self, raw_path, y_raw):
            self.raw_path = raw_path
            self.ports = {
                'A': [(0, Seg("1'b0"))],
                'B': [(0, Seg("1'b1"))],
                'Y': [(0, Seg(y_raw))],
            }

    inst1 = Inst('m.g1', 'm.w1.0')
    inst2 = Inst('m.g2', 'm.out.0')

    boundary, const_count, is_deg = boundary_extractor.extract_boundary([inst1, inst2])
    assert is_deg is True
    assert boundary.output.raw == 'm.out.0'
    assert const_count >= 2


def test_extract_boundary_normal_chain(module_with_or_chain, boundary_extractor):
    module_with_or_chain.optimize()
    insts = [
        module_with_or_chain.instances['or1'],
        module_with_or_chain.instances['or2'],
        module_with_or_chain.instances['or3'],
    ]
    boundary, const_count, is_deg = boundary_extractor.extract_boundary(insts)
    assert is_deg is False
    assert len(boundary.inputs) == 4
    assert boundary.output is not None
    assert len(boundary.internal_wires) == 2
    assert const_count == 0


def test_analyze_module_gates_counts_correctly(module_with_or_chain, or_config):
    module_with_or_chain.optimize()
    analysis = co.analyze_module_gates(module_with_or_chain, or_config)
    assert analysis.total_gates == 3


def test_analyze_module_gates_empty_module(empty_module, or_config):
    analysis = co.analyze_module_gates(empty_module, or_config)
    assert analysis.total_gates == 0


def test_analyze_module_gates_wrong_type(module_with_or_chain, and_config):
    module_with_or_chain.optimize()
    analysis = co.analyze_module_gates(module_with_or_chain, and_config)
    assert analysis.total_gates == 0


def test_gate_tree_builder_depth(or_config):
    for n_inputs in [2, 3, 4, 5, 8, 16]:
        m = Module(raw_path='t')
        for i in range(n_inputs):
            m.create_wire(f'in{i}')
        m.create_wire('out')
        for i in range(max(0, n_inputs - 2)):
            m.create_wire(f'int{i}')

        inputs = [WireSegmentPath(raw=f't.in{i}.0') for i in range(n_inputs)]
        output = WireSegmentPath(raw='t.out.0')
        internal = [WireSegmentPath(raw=f't.int{i}.0') for i in range(max(0, n_inputs - 2))]
        boundary = co.ChainBoundary(inputs=inputs, output=output, internal_wires=internal)

        b = co.GateTreeBuilder(m, 'pfx', boundary, or_config)
        b.build()

        assert b.level == math.ceil(math.log2(n_inputs))


def test_gate_tree_builder_odd_passthrough(empty_module, or_config):
    for i in range(3):
        empty_module.create_wire(f'in{i}')
    empty_module.create_wire('out')
    empty_module.create_wire('int0')

    boundary = co.ChainBoundary(
        inputs=[WireSegmentPath(raw=f'test_module.in{i}.0') for i in range(3)],
        output=WireSegmentPath(raw='test_module.out.0'),
        internal_wires=[WireSegmentPath(raw='test_module.int0.0')],
    )
    b = co.GateTreeBuilder(empty_module, 'odd', boundary, or_config)
    b.build()
    assert len(empty_module.instances) == 2


def test_gate_tree_builder_creates_new_wires_when_internal_missing(empty_module, or_config):
    for i in range(4):
        empty_module.create_wire(f'in{i}')
    empty_module.create_wire('out')

    before = len(empty_module.wires)

    boundary = co.ChainBoundary(
        inputs=[WireSegmentPath(raw=f'test_module.in{i}.0') for i in range(4)],
        output=WireSegmentPath(raw='test_module.out.0'),
        internal_wires=[],
    )
    b = co.GateTreeBuilder(empty_module, 'nw', boundary, or_config)
    b.build()

    assert len(empty_module.wires) > before


def test_gate_tree_builder_reuses_internal_wires(empty_module, or_config):
    for i in range(4):
        empty_module.create_wire(f'in{i}')
    empty_module.create_wire('out')
    empty_module.create_wire('int0')
    empty_module.create_wire('int1')

    boundary = co.ChainBoundary(
        inputs=[WireSegmentPath(raw=f'test_module.in{i}.0') for i in range(4)],
        output=WireSegmentPath(raw='test_module.out.0'),
        internal_wires=[
            WireSegmentPath(raw='test_module.int0.0'),
            WireSegmentPath(raw='test_module.int1.0'),
        ],
    )

    before = len(empty_module.wires)
    b = co.GateTreeBuilder(empty_module, 'reuse', boundary, or_config)
    b.build()

    assert len(empty_module.wires) == before


def test_gate_tree_builder_two_inputs(empty_module, or_config):
    empty_module.create_wire('in0')
    empty_module.create_wire('in1')
    empty_module.create_wire('out')

    boundary = co.ChainBoundary(
        inputs=[WireSegmentPath(raw='test_module.in0.0'), WireSegmentPath(raw='test_module.in1.0')],
        output=WireSegmentPath(raw='test_module.out.0'),
        internal_wires=[],
    )
    b = co.GateTreeBuilder(empty_module, 'two', boundary, or_config)
    b.build()

    assert len(empty_module.instances) == 1
    assert b.level == 1


def test_build_instance_lookup_and_fuzzy_find(module_with_or_chain):
    lookup = co.build_instance_lookup(module_with_or_chain)
    assert len(lookup) > 0
    assert any('or1' in str(k) for k in lookup.keys())

    assert co.fuzzy_find_instance(module_with_or_chain, 'or1') is not None
    assert co.fuzzy_find_instance(module_with_or_chain, 'nonexistent_xyz') is None


def test_fuzzy_find_instance_suffix_match(module_with_or_chain):
    result = co.fuzzy_find_instance(module_with_or_chain, '1')
    assert result is not None


def test_fuzzy_find_instance_contains_match(module_with_or_chain):
    result = co.fuzzy_find_instance(module_with_or_chain, 'r2')
    assert result is not None


def test_fuzzy_find_instance_multiple_suffix_shortest(module_with_or_chain):
    result = co.fuzzy_find_instance(module_with_or_chain, 'or')
    assert result is not None


def test_resolve_chain_instances_valid_and_invalid(module_with_or_chain):
    module_with_or_chain.optimize()
    keys_full = ['or_chain_module.or1', 'or_chain_module.or2', 'or_chain_module.or3']
    insts = co.resolve_chain_instances(module_with_or_chain, keys_full)
    assert len(insts) == 3

    with pytest.raises(KeyError, match='Could not resolve'):
        co.resolve_chain_instances(module_with_or_chain, ['nope1', 'nope2'])


def test_resolve_chain_instances_short_names(module_with_or_chain):
    module_with_or_chain.optimize()
    insts = co.resolve_chain_instances(module_with_or_chain, ['or1', 'or2'])
    assert len(insts) == 2


def test_remove_instances_handles_exception():
    m = Module(raw_path='t')

    class FakeInstance:
        raw_path = 'fake'

    co.remove_instances(m, [FakeInstance()])


def test_remove_instances_actually_removes(module_with_or_chain):
    module_with_or_chain.optimize()
    initial = len(module_with_or_chain.instances)
    inst = module_with_or_chain.instances['or1']
    co.remove_instances(module_with_or_chain, [inst])
    assert len(module_with_or_chain.instances) == initial - 1


def test_replace_chain_empty_keys(empty_module, or_config, chain_replacer):
    info = chain_replacer.replace_chain(empty_module, [], 'pfx', or_config)
    assert info.status == co.ChainStatus.SKIPPED_RESOLUTION_FAILED
    assert info.was_replaced is False


def test_replace_chain_resolution_failed(empty_module, or_config, chain_replacer):
    info = chain_replacer.replace_chain(empty_module, ['nope1', 'nope2'], 'pfx', or_config)
    assert info.status == co.ChainStatus.SKIPPED_RESOLUTION_FAILED
    assert 'Could not resolve' in (info.error_message or '')


def test_replace_chain_degenerate(monkeypatch, or_config):
    boundary = co.ChainBoundary(
        inputs=[WireSegmentPath(raw='m.in1.0')],
        output=WireSegmentPath(raw='m.out.0'),
        internal_wires=[],
    )

    replacer = co.ChainReplacer(boundary_extractor=co.ChainBoundaryExtractor())

    monkeypatch.setattr(co, 'resolve_chain_instances', lambda module, keys: ['dummy_inst'])
    monkeypatch.setattr(
        replacer.boundary_extractor,
        'extract_boundary',
        lambda insts: (boundary, 3, True),
    )

    info = replacer.replace_chain(module=object(), chain_keys=['a', 'b'], prefix='pfx', cfg=or_config)
    assert info.status == co.ChainStatus.SKIPPED_DEGENERATE


def test_replace_chain_boundary_failed(monkeypatch, or_config):
    replacer = co.ChainReplacer(boundary_extractor=co.ChainBoundaryExtractor())
    monkeypatch.setattr(co, 'resolve_chain_instances', lambda module, keys: ['dummy_inst'])

    def boom(_insts):
        raise RuntimeError('nope')

    monkeypatch.setattr(replacer.boundary_extractor, 'extract_boundary', boom)

    info = replacer.replace_chain(module=object(), chain_keys=['a', 'b'], prefix='pfx', cfg=or_config)
    assert info.status == co.ChainStatus.SKIPPED_BOUNDARY_FAILED
    assert 'nope' in (info.error_message or '')


def test_replace_chain_disconnect_failed(monkeypatch, or_config):
    boundary = co.ChainBoundary(
        inputs=[WireSegmentPath(raw='m.in1.0'), WireSegmentPath(raw='m.in2.0')],
        output=WireSegmentPath(raw='m.out.0'),
        internal_wires=[],
    )

    replacer = co.ChainReplacer(boundary_extractor=co.ChainBoundaryExtractor())
    monkeypatch.setattr(co, 'resolve_chain_instances', lambda module, keys: ['dummy_inst'])
    monkeypatch.setattr(replacer.boundary_extractor, 'extract_boundary', lambda insts: (boundary, 0, False))
    monkeypatch.setattr(co, 'remove_instances', lambda module, insts: (_ for _ in ()).throw(RuntimeError('rmfail')))

    info = replacer.replace_chain(module=object(), chain_keys=['a', 'b'], prefix='pfx', cfg=or_config)
    assert info.status == co.ChainStatus.SKIPPED_DISCONNECT_FAILED
    assert 'rmfail' in (info.error_message or '')


def test_replace_chain_tree_build_raises(monkeypatch, or_config):
    boundary = co.ChainBoundary(
        inputs=[WireSegmentPath(raw='m.in1.0'), WireSegmentPath(raw='m.in2.0')],
        output=WireSegmentPath(raw='m.out.0'),
        internal_wires=[],
    )

    replacer = co.ChainReplacer(boundary_extractor=co.ChainBoundaryExtractor())
    monkeypatch.setattr(co, 'resolve_chain_instances', lambda module, keys: ['dummy_inst'])
    monkeypatch.setattr(replacer.boundary_extractor, 'extract_boundary', lambda insts: (boundary, 0, False))
    monkeypatch.setattr(co, 'remove_instances', lambda module, insts: None)

    class BadBuilder:
        def __init__(self, *a, **k):
            pass

        def build(self):
            raise RuntimeError('boom')

    monkeypatch.setattr(co, 'GateTreeBuilder', BadBuilder)

    with pytest.raises(RuntimeError, match='Tree build failed'):
        replacer.replace_chain(module=object(), chain_keys=['a', 'b'], prefix='pfx', cfg=or_config)


def test_replace_chain_success_integration(module_with_or_chain, or_config):
    module_with_or_chain.optimize()
    chains = co.find_gate_chains_netlist(module_with_or_chain, or_config)
    assert len(chains) == 1

    replacer = co.ChainReplacer(boundary_extractor=co.ChainBoundaryExtractor())
    info = replacer.replace_chain(module_with_or_chain, chains[0], 'pfx', or_config)

    assert info.status == co.ChainStatus.REPLACED
    assert info.was_replaced is True
    assert info.num_inputs == 4


def test_invalidate_graph_cache(module_with_or_chain):
    _ = module_with_or_chain.graph()
    co.invalidate_graph_cache(module_with_or_chain)


def test_invalidate_graph_cache_no_graph(empty_module):
    co.invalidate_graph_cache(empty_module)


def test_fix_invalid_verilog(tmp_path):
    f = tmp_path / 't.v'
    f.write_text("module t;\n  assign 1'bx = c;\n  assign a = b;\n  assign 1'b0 = d;\nendmodule\n")
    removed = co.fix_invalid_verilog(str(f))
    assert removed == 2
    txt = f.read_text()
    assert "assign 1'bx" not in txt
    assert "assign 1'b0" not in txt
    assert 'assign a = b' in txt


def test_fix_invalid_verilog_no_changes(tmp_path):
    f = tmp_path / 'clean.v'
    f.write_text('module t;\n  assign a = b;\nendmodule\n')
    removed = co.fix_invalid_verilog(str(f))
    assert removed == 0


class DummySeg:
    def __init__(self, raw, raise_ws_path=False):
        self._raw = raw
        self._raise_ws_path = raise_ws_path

    @property
    def ws_path(self):
        if self._raise_ws_path:
            raise AttributeError('ws_path broken')
        return WireSegmentPath(raw=self._raw)


class DummyInst:
    def __init__(self, raw_path, inst_type, ports):
        self.raw_path = raw_path
        self.instance_type = inst_type
        self.ports = ports


class DummyModuleDeg:
    def __init__(self, instances):
        self.instances = dict(instances)

    def remove_instance(self, inst):
        for k, v in list(self.instances.items()):
            if v is inst:
                del self.instances[k]
                return
        raise KeyError('not found')


def test_remove_degenerate_gates_or_and_xor_basic():
    or_cfg = co.get_gate_config('or')
    inst_or = DummyInst(
        'm.or1',
        '§or',
        {'A': [(0, DummySeg("1'b0"))], 'B': [(0, DummySeg("1'b1"))], 'Y': [(0, DummySeg('m.out.0'))]},
    )
    m = DummyModuleDeg({'or1': inst_or})
    assert co.remove_degenerate_gates(m, or_cfg) == 1
    assert m.instances == {}

    and_cfg = co.get_gate_config('and')
    inst_and = DummyInst(
        'm.and1',
        '§and',
        {'A': [(0, DummySeg("1'b1"))], 'B': [(0, DummySeg("1'b0"))], 'Y': [(0, DummySeg('m.out.0'))]},
    )
    m2 = DummyModuleDeg({'and1': inst_and})
    assert co.remove_degenerate_gates(m2, and_cfg) == 1

    xor_cfg = co.get_gate_config('xor')
    inst_xor = DummyInst(
        'm.xor1',
        '§xor',
        {'A': [(0, DummySeg("1'b1"))], 'B': [(0, DummySeg("1'b1"))], 'Y': [(0, DummySeg('m.out.0'))]},
    )
    m3 = DummyModuleDeg({'xor1': inst_xor})
    assert co.remove_degenerate_gates(m3, xor_cfg) == 0
    assert 'xor1' in m3.instances


def test_remove_degenerate_gates_nand_nor():
    try:
        nand_cfg = co.get_gate_config('nand')
        inst_nand = DummyInst(
            'm.nand1',
            '§nand',
            {'A': [(0, DummySeg("1'b0"))], 'B': [(0, DummySeg("1'b1"))], 'Y': [(0, DummySeg('m.out.0'))]},
        )
        m = DummyModuleDeg({'nand1': inst_nand})
        co.remove_degenerate_gates(m, nand_cfg)
    except ValueError:
        pytest.skip('NAND gate not available')

    try:
        nor_cfg = co.get_gate_config('nor')
        inst_nor = DummyInst(
            'm.nor1',
            '§nor',
            {'A': [(0, DummySeg("1'b0"))], 'B': [(0, DummySeg("1'b0"))], 'Y': [(0, DummySeg('m.out.0'))]},
        )
        m2 = DummyModuleDeg({'nor1': inst_nor})
        co.remove_degenerate_gates(m2, nor_cfg)
    except ValueError:
        pytest.skip('NOR gate not available')


def test_remove_degenerate_gates_more_continue_branches():
    cfg = co.get_gate_config('or')

    i_bad_type = DummyInst(
        'm.bad',
        '§and',
        {'A': [(0, DummySeg("1'b0"))], 'B': [(0, DummySeg("1'b0"))], 'Y': [(0, DummySeg('m.o.0'))]},
    )

    i_no_y = DummyInst(
        'm.no_y',
        '§or',
        {'A': [(0, DummySeg("1'b0"))], 'B': [(0, DummySeg("1'b0"))]},
    )

    i_multi_y = DummyInst(
        'm.multi',
        '§or',
        {
            'A': [(0, DummySeg("1'b0"))],
            'B': [(0, DummySeg("1'b0"))],
            'Y': [(0, DummySeg('m.o1.0')), (1, DummySeg('m.o2.0'))],
        },
    )

    i_inv_y = DummyInst(
        'm.inv',
        '§or',
        {'A': [(0, DummySeg("1'b0"))], 'B': [(0, DummySeg("1'b0"))], 'Y': [(0, DummySeg('0'))]},
    )

    i_real_in = DummyInst(
        'm.real',
        '§or',
        {'A': [(0, DummySeg('m.in.0'))], 'B': [(0, DummySeg("1'b0"))], 'Y': [(0, DummySeg('m.o.0'))]},
    )

    m = DummyModuleDeg({'bad': i_bad_type, 'noy': i_no_y, 'multi': i_multi_y, 'inv': i_inv_y, 'real': i_real_in})
    assert co.remove_degenerate_gates(m, cfg) == 0
    assert set(m.instances.keys()) == {'bad', 'noy', 'multi', 'inv', 'real'}


def test_remove_degenerate_gates_port_none_branch():
    cfg = co.get_gate_config('or')

    i_no_a = DummyInst(
        'm.no_a',
        '§or',
        {'B': [(0, DummySeg("1'b0"))], 'Y': [(0, DummySeg('m.o.0'))]},
    )
    m = DummyModuleDeg({'no_a': i_no_a})
    co.remove_degenerate_gates(m, cfg)


def test_remove_degenerate_gates_remove_instance_exception_is_caught():
    cfg = co.get_gate_config('or')
    inst_or = DummyInst(
        'm.or1',
        '§or',
        {'A': [(0, DummySeg("1'b0"))], 'B': [(0, DummySeg("1'b0"))], 'Y': [(0, DummySeg('m.out.0'))]},
    )

    class M:
        def __init__(self):
            self.instances = {'or1': inst_or}

        def remove_instance(self, inst):
            raise RuntimeError('cannot remove')

    m = M()
    assert co.remove_degenerate_gates(m, cfg) == 0
    assert 'or1' in m.instances


def test_scan_module_subprocess_ok(monkeypatch, scanner):
    class R:
        returncode = 0
        stdout = json.dumps([['a', 'b']])
        stderr = ''

    monkeypatch.setattr(co.subprocess, 'run', lambda *a, **k: R())
    assert scanner.scan_module('in.v', 'TOP', 'm1', 'or') == [['a', 'b']]


def test_scan_module_subprocess_default_python(monkeypatch):
    class R:
        returncode = 0
        stdout = json.dumps([['a']])
        stderr = ''

    monkeypatch.setattr(co.subprocess, 'run', lambda *a, **k: R())
    s = co.GateChainScanner(script_path=co.__file__, python=None)
    result = s.scan_module('in.v', 'TOP', 'm1', 'or')
    assert result == [['a']]


def test_scan_module_subprocess_fail(monkeypatch, scanner):
    class R:
        returncode = 1
        stdout = ''
        stderr = 'err'

    monkeypatch.setattr(co.subprocess, 'run', lambda *a, **k: R())
    with pytest.raises(RuntimeError):
        scanner.scan_module('in.v', 'TOP', 'm1', 'or')


def test_collect_chains_subprocess_aggregates(monkeypatch, scanner):
    def fake_scan(_input_path, _top, module, _gate):
        if module == 'm1':
            return [['x', 'y']]
        if module == 'm2':
            return []
        return [['a', 'b'], ['c', 'd']]

    monkeypatch.setattr(scanner, 'scan_module', fake_scan)

    out = scanner.collect_chains(
        input_path='dummy.v',
        top='TOP',
        modules=['m1', 'm2', 'm3'],
        gate='or',
    )
    assert set(out.keys()) == {'m1', 'm3'}
    assert out['m1'] == [['x', 'y']]
    assert len(out['m3']) == 2


class DummyModOpt:
    def __init__(self, name):
        self.name = name
        self.instances = {}
        self._graph = object()

    def optimize(self):
        pass

    def split_all(self, _):
        pass


class DummyCircuitOpt:
    def __init__(self, name, modules):
        self.name = name
        self.modules = modules

    def __iter__(self):  # type: ignore
        """Iterator over the modules in the circuit."""
        return iter(self.modules.values())

    def write(self, path, overwrite=True):
        with open(path, 'w') as f:
            f.write('module t;\n')
            f.write("  assign 1'bx = c;\n")
            f.write('  assign a = b;\n')
            f.write("  assign 1'b0 = d;\n")
            f.write('endmodule\n')


def _noop_log_report(self, _log):
    return None


def test_optimize_circuit_gates_as_string(monkeypatch):
    circ = DummyCircuitOpt('C', {'m1': DummyModOpt('m1')})
    monkeypatch.setattr(co, 'nc_read', lambda input_path, top: circ)

    monkeypatch.setattr(co.GateChainScanner, 'collect_chains', lambda *a, **k: {})
    monkeypatch.setattr(co.CircuitOptimizationResult, '_log_report', _noop_log_report)

    res = co.optimize_circuit('dummy.v', 'TOP', gates='or')
    assert res.modules_processed == 1


def test_optimize_circuit_gates_as_list(monkeypatch):
    circ = DummyCircuitOpt('C', {'m1': DummyModOpt('m1')})
    monkeypatch.setattr(co, 'nc_read', lambda input_path, top: circ)

    monkeypatch.setattr(co.GateChainScanner, 'collect_chains', lambda *a, **k: {})
    monkeypatch.setattr(co.CircuitOptimizationResult, '_log_report', _noop_log_report)

    res = co.optimize_circuit('dummy.v', 'TOP', gates=['or', 'and'])
    assert res.modules_processed == 1


def test_optimize_circuit_with_chains(monkeypatch, tmp_path):
    mod = DummyModOpt('m1')
    circ = DummyCircuitOpt('C', {'m1': mod})

    monkeypatch.setattr(co, 'nc_read', lambda input_path, top: circ)

    def fake_collect(self, *a, **k):
        return {'m1': [['g1', 'g2']]}

    monkeypatch.setattr(co.GateChainScanner, 'collect_chains', fake_collect)

    def fake_replace(self, module, chain_keys, prefix, cfg):
        return co.ChainInfo(
            chain_keys=list(chain_keys),
            status=co.ChainStatus.REPLACED,
            num_gates=len(chain_keys),
            num_inputs=3,
        )

    monkeypatch.setattr(co.ChainReplacer, 'replace_chain', fake_replace)

    monkeypatch.setattr(co.CircuitOptimizationResult, '_log_report', _noop_log_report)

    out_file = tmp_path / 'out.v'
    res = co.optimize_circuit('dummy.v', 'TOP', gates='or', output_path=str(out_file))

    assert res.total_chains_replaced == 1


def test_optimize_circuit_with_skip_modules(monkeypatch):
    circ = DummyCircuitOpt('C', {'m1': DummyModOpt('m1'), 'm2': DummyModOpt('m2')})
    monkeypatch.setattr(co, 'nc_read', lambda input_path, top: circ)

    monkeypatch.setattr(co.GateChainScanner, 'collect_chains', lambda *a, **k: {})
    monkeypatch.setattr(co.CircuitOptimizationResult, '_log_report', _noop_log_report)

    res = co.optimize_circuit('dummy.v', 'TOP', gates='or', skip_modules={'m1'})
    assert res.modules_processed == 2


def test_optimize_circuit_with_remove_degenerate(monkeypatch):
    circ = DummyCircuitOpt('C', {'m1': DummyModOpt('m1')})
    monkeypatch.setattr(co, 'nc_read', lambda input_path, top: circ)

    monkeypatch.setattr(co.GateChainScanner, 'collect_chains', lambda *a, **k: {})
    monkeypatch.setattr(co, 'remove_degenerate_gates', lambda *a, **k: 5)
    monkeypatch.setattr(co.CircuitOptimizationResult, '_log_report', _noop_log_report)

    res = co.optimize_circuit('dummy.v', 'TOP', gates='or', remove_degenerate=True)
    assert res.modules_processed == 1


def test_optimize_circuit_chain_replace_exception(monkeypatch):
    mod = DummyModOpt('m1')
    circ = DummyCircuitOpt('C', {'m1': mod})

    monkeypatch.setattr(co, 'nc_read', lambda input_path, top: circ)

    monkeypatch.setattr(co.GateChainScanner, 'collect_chains', lambda *a, **k: {'m1': [['g1', 'g2']]})

    def fake_replace(self, *a, **k):
        raise RuntimeError('boom')

    monkeypatch.setattr(co.ChainReplacer, 'replace_chain', fake_replace)

    monkeypatch.setattr(co.CircuitOptimizationResult, '_log_report', _noop_log_report)

    res = co.optimize_circuit('dummy.v', 'TOP', gates='or')
    assert res.total_chains_failed == 1


def test_optimize_circuit_chain_skipped(monkeypatch):
    mod = DummyModOpt('m1')
    circ = DummyCircuitOpt('C', {'m1': mod})

    monkeypatch.setattr(co, 'nc_read', lambda input_path, top: circ)
    monkeypatch.setattr(co.GateChainScanner, 'collect_chains', lambda *a, **k: {'m1': [['g1', 'g2']]})

    def fake_replace(self, _module, chain_keys, _prefix, _cfg):
        return co.ChainInfo(
            chain_keys=list(chain_keys),
            status=co.ChainStatus.SKIPPED_DEGENERATE,
            num_gates=len(chain_keys),
        )

    monkeypatch.setattr(co.ChainReplacer, 'replace_chain', fake_replace)

    monkeypatch.setattr(co.CircuitOptimizationResult, '_log_report', _noop_log_report)

    res = co.optimize_circuit('dummy.v', 'TOP', gates='or')
    assert res.total_chains_skipped == 1


if __name__ == '__main__':
    pytest.main(['-q', os.path.basename(__file__)])
