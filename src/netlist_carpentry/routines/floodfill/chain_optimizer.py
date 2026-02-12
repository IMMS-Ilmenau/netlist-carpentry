"""
Gate-Chain Optimizer - Detects and replaces linear 2-input gate chains with balanced trees.

Supports gate type (or/and) with A, B inputs and Y output.
Uses subprocess-based scanning for memory safety on large designs.
"""

from __future__ import annotations

import gc
import json
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Type, Union

from netlist_carpentry import Circuit, Direction, Instance, Module, ModuleGraph, PortSegment
from netlist_carpentry import read as nc_read
from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath
from netlist_carpentry.core.netlist_elements.segment_base import _Segment
from netlist_carpentry.routines.floodfill.chain_metrics import (
    ChainBoundary,
    ChainInfo,
    ChainStatus,
    CircuitOptimizationResult,
    GateAnalysis,
    ModuleReport,
    ReplacementResult,
)
from netlist_carpentry.utils.gate_lib_base_classes import PrimitiveGate
from netlist_carpentry.utils.log import LOG


@dataclass(frozen=True)
class GateConfig:
    """Configuration for a 2-input gate type."""

    name: str
    nsubtype: str
    chain_prefix: str
    gate_cls: Type[PrimitiveGate]


def get_gate_config(gate: str) -> GateConfig:
    """Resolve gate string ("or" or "§or") into GateConfig."""
    from netlist_carpentry.utils.gate_lib import get

    gate_name = gate.lstrip('§').strip().lower()
    if not gate_name:
        raise ValueError('Gate must not be empty')

    gate_cls = get('§' + gate_name)
    if gate_cls is None:
        raise ValueError(f"Unsupported gate '{gate_name}'. Expected '{gate_name}' in netlist_carpentry.utils.gate_lib.")

    return GateConfig(
        name=gate_name,
        nsubtype=f'§{gate_name}',
        chain_prefix=f'{gate_name}_chain',
        gate_cls=gate_cls,
    )


def _normalize_gates(gates: Union[str, List[str]]) -> List[str]:
    """Normalize gates input to a list."""
    return [gates] if isinstance(gates, str) else list(gates)


def is_gate(graph: ModuleGraph, node: str, cfg: GateConfig, *, exclude_chains: bool = True) -> bool:
    """Check if node is a gate instance of the configured type."""
    if graph.node_type(node) != 'INSTANCE':
        return False
    if graph.node_subtype(node) != cfg.nsubtype:
        return False
    if exclude_chains:
        instance_name = str(node).split('.')[-1]
        if instance_name.startswith(cfg.chain_prefix):
            return False
    return True


def is_chain_head(graph: ModuleGraph, node: str, gate_nodes: Set[str]) -> bool:
    """Check if node is start of a chain (no gate predecessors)."""
    if node not in gate_nodes:
        return False
    return not any(pred in gate_nodes for pred in graph.predecessors(node))


def build_chain(graph: ModuleGraph, start: str, gate_nodes: Set[str]) -> List[str]:
    """Build chain by following single gate successors."""
    chain = [start]
    current = start
    while True:
        successors = [s for s in graph.successors(current) if s in gate_nodes and s not in chain]
        if len(successors) != 1:
            break
        current = successors[0]
        chain.append(current)
    return chain


def find_gate_chains(graph: ModuleGraph, cfg: GateConfig) -> List[List[str]]:
    """Find all gate chains (length >= 2) in graph."""
    gate_nodes = {n for n in graph.nodes if is_gate(graph, n, cfg)}
    visited: Set[str] = set()
    chains: List[List[str]] = []

    for node in gate_nodes:
        if node in visited or not is_chain_head(graph, node, gate_nodes):
            continue
        chain = build_chain(graph, node, gate_nodes)
        if len(chain) > 1:
            chains.append(chain)
            visited.update(chain)

    return chains


def extract_instance_key(graph: ModuleGraph, node: str) -> str:
    """Extract instance identifier from node attributes."""
    node_data = graph.nodes.get(node, {})
    for key in ('raw_path', 'path', 'instance_path', 'raw', 'name'):
        value = node_data.get(key)
        if isinstance(value, str) and value:
            return value
    return str(node)


def safe_get_driver(segment: _Segment) -> Any:
    """Safely get wire segment driver."""
    try:
        return segment.driver()
    except Exception:
        return None


def safe_get_wire_path(segment: PortSegment) -> Optional[WireSegmentPath]:
    """Safely get wire segment path."""
    try:
        return segment.ws_path
    except Exception:
        return None


def is_valid_wire_path(wire_path: Optional[WireSegmentPath]) -> bool:
    """Check if wire path is valid."""
    if wire_path is None:
        return False
    raw = getattr(wire_path, 'raw', '')
    return bool(raw) and raw != '0'


def is_constant_wire(wire_path: Optional[WireSegmentPath]) -> bool:
    """Check if wire path is a constant (0, 1, x, z, 1'b0, etc.)."""
    if wire_path is None:
        return True
    raw = getattr(wire_path, 'raw', '')
    if not raw:
        return True
    if raw in ('0', '1', 'x', 'z', 'X', 'Z'):
        return True
    if raw.startswith("1'b") or raw.startswith("1'B"):
        return True
    return False


def _driver_in_chain(segment, chain_ids: Set[str]) -> bool:
    """Return True if the driver of `segment` belongs to a gate instance in `chain_ids`."""
    driver = safe_get_driver(segment)
    if not driver:
        return False

    port = getattr(driver, 'port', None)
    parent = getattr(port, 'parent', None) if port else None
    raw_path = getattr(parent, 'raw_path', None) if parent else None
    return bool(raw_path and raw_path in chain_ids)


def _should_include_external_wire(
    wire_path: Optional[WireSegmentPath],
    segment,
    chain_ids: Set[str],
    internal_wire_paths: Set[str],
) -> Tuple[bool, bool]:
    """Return (include, is_constant).

    include is True if this wire should be collected as an external input.
    is_constant is True if wire_path is a constant wire.
    """
    if is_constant_wire(wire_path):
        return False, True

    if not is_valid_wire_path(wire_path):
        return False, False

    raw = getattr(wire_path, 'raw', '')
    if not raw:
        return False, False

    if raw in internal_wire_paths:
        return False, False

    if _driver_in_chain(segment, chain_ids):
        return False, False

    return True, False


def is_target_gate(instance: Instance, cfg: GateConfig, *, exclude_chains: bool = True) -> bool:
    """Check if instance is a gate of the configured type."""
    if instance.instance_type != cfg.nsubtype:
        return False
    if exclude_chains:
        name = instance.raw_path.split('.')[-1] if instance.raw_path else ''
        if name.startswith(cfg.chain_prefix):
            return False
    return True


def _collect_target_gates(module: Module, cfg: GateConfig) -> Dict[str, Instance]:
    return {inst.raw_path: inst for inst in module.instances.values() if is_target_gate(inst, cfg)}


def _build_wire_to_driver(gates: Dict[str, Instance]) -> Dict[str, str]:
    wire_to_driver: Dict[str, str] = {}
    for path, inst in gates.items():
        port_y = inst.ports.get('Y')
        if port_y is None:
            continue
        for _, segment in port_y:
            wire_path = safe_get_wire_path(segment)
            raw = getattr(wire_path, 'raw', '') if wire_path else ''
            if raw:
                wire_to_driver[raw] = path
    return wire_to_driver


def _build_predecessors_successors(
    gates: Dict[str, Instance],
    wire_to_driver: Dict[str, str],
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    predecessors: Dict[str, Set[str]] = {path: set() for path in gates}
    successors: Dict[str, Set[str]] = {path: set() for path in gates}

    for path, inst in gates.items():
        for port_name in ('A', 'B'):
            port = inst.ports.get(port_name)
            if port is None:
                continue
            for _, segment in port:
                wire_path = safe_get_wire_path(segment)
                raw = wire_path.raw if wire_path else ''
                if not raw:
                    continue

                driver_gate = wire_to_driver.get(raw)
                if driver_gate and driver_gate != path:
                    predecessors[path].add(driver_gate)
                    successors[driver_gate].add(path)

    return predecessors, successors


def build_gate_connectivity(
    module: Module,
    cfg: GateConfig,
) -> Tuple[Dict[str, Instance], Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Build connectivity maps for target gates."""
    gates = _collect_target_gates(module, cfg)
    if not gates:
        return {}, {}, {}

    wire_to_driver = _build_wire_to_driver(gates)
    predecessors, successors = _build_predecessors_successors(gates, wire_to_driver)
    return gates, predecessors, successors


def _chain_heads(predecessors: Dict[str, Set[str]]) -> List[str]:
    return [path for path, preds in predecessors.items() if not preds]


def _next_gate(successors: Dict[str, Set[str]], current: str, visited: Set[str], chain: List[str]) -> Optional[str]:
    candidates = [s for s in successors.get(current, set()) if s not in chain and s not in visited]
    return candidates[0] if len(candidates) == 1 else None


def find_gate_chains_netlist(module: Module, cfg: GateConfig) -> List[List[str]]:
    """Find all gate chains (length >= 2) directly from netlist."""
    gates, predecessors, successors = build_gate_connectivity(module, cfg)
    if not gates:
        return []

    chains: List[List[str]] = []
    visited: Set[str] = set()

    for head in _chain_heads(predecessors):
        if head in visited:
            continue
        chain = [head]
        current = head
        while True:
            nxt = _next_gate(successors, current, visited, chain)
            if nxt is None:
                break
            chain.append(nxt)
            current = nxt

        if len(chain) > 1:
            chains.append(chain)
            visited.update(chain)

    return chains


def analyze_module_gates(module: Module, cfg: GateConfig) -> GateAnalysis:
    """Analyze gates by input count."""
    analysis = GateAnalysis()

    for instance in module.instances.values():
        if instance.instance_type != cfg.nsubtype:
            continue

        real_inputs = 0
        has_constant = False

        for port_name in ('A', 'B'):
            port = instance.ports.get(port_name)
            if port is None:
                continue
            for _, segment in port:
                wire_path = safe_get_wire_path(segment)
                if is_constant_wire(wire_path):
                    has_constant = True
                elif is_valid_wire_path(wire_path):
                    real_inputs += 1

        analysis.add_gate(real_inputs, has_constant)

    return analysis


class GateTreeBuilder:
    """Builds a balanced gate tree from input wires."""

    def __init__(self, module: Module, prefix: str, boundary: ChainBoundary, cfg: GateConfig) -> None:
        self.module = module
        self.prefix = prefix
        self.boundary = boundary
        self.cfg = cfg
        self.available_wires = list(boundary.internal_wires)
        self.level = 0

    def build(self) -> None:
        wires = list(self.boundary.inputs)
        while len(wires) > 1:
            wires = self._build_level(wires)
            self.level += 1

    def _build_level(self, inputs: List[WireSegmentPath]) -> List[WireSegmentPath]:
        outputs: List[WireSegmentPath] = []
        for i in range(0, len(inputs), 2):
            if i + 1 < len(inputs):
                is_final = len(inputs) == 2
                outputs.append(self._create_gate(inputs[i], inputs[i + 1], i // 2, is_final))
            else:
                outputs.append(inputs[i])
        return outputs

    def _create_gate(self, a: WireSegmentPath, b: WireSegmentPath, idx: int, is_final: bool) -> WireSegmentPath:
        name = f'{self.prefix}_L{self.level}_N{idx}'
        path = f'{self.module.name}.{name}'

        gate = self.cfg.gate_cls(raw_path=path)
        self.module.add_instance(gate)
        gate.connect_modify('A', ws_path=a, direction=Direction.IN, index=0)
        gate.connect_modify('B', ws_path=b, direction=Direction.IN, index=0)

        out_wire = self._alloc_output(is_final, name)
        gate.connect_modify('Y', ws_path=out_wire, direction=Direction.OUT, index=0)
        return out_wire

    def _alloc_output(self, is_final: bool, name: str) -> WireSegmentPath:
        if is_final:
            return self.boundary.output
        if self.available_wires:
            return self.available_wires.pop(0)
        wire = self.module.create_wire(wire_name=f'{name}_Y', width=1)
        return WireSegmentPath(raw=f'{self.module.name}.{wire.name}.0')


class ChainBoundaryExtractor:
    """Extracts ChainBoundary and constant-input stats for a chain."""

    def collect_external_inputs(
        self,
        chain_instances: Sequence[Instance],
        chain_ids: Set[str],
        internal_wire_paths: Optional[Set[str]] = None,
    ) -> Tuple[List[WireSegmentPath], int]:
        """Collect external input wires. Returns (inputs, constant_count)."""
        internal_wire_paths = internal_wire_paths or set()
        seen: Dict[str, WireSegmentPath] = {}
        constant_count = 0

        for instance in chain_instances:
            for port_name in ('A', 'B'):
                port = instance.ports.get(port_name)
                if port is None:
                    continue

                for _, segment in port:
                    wire_path = safe_get_wire_path(segment)
                    include, is_const = _should_include_external_wire(wire_path, segment, chain_ids, internal_wire_paths)
                    if is_const:
                        constant_count += 1
                        continue
                    if include:
                        seen[wire_path.raw] = wire_path

        return list(seen.values()), constant_count

    def collect_output_wires(self, chain_instances: Sequence[Instance]) -> Tuple[WireSegmentPath, List[WireSegmentPath]]:
        """Collect output wire and internal wires from chain."""
        internal_wires: List[WireSegmentPath] = []
        tail = chain_instances[-1]
        output_wire: Optional[WireSegmentPath] = None

        for instance in chain_instances:
            port = instance.ports.get('Y')
            if port is None:
                raise RuntimeError(f'{instance.raw_path}: missing port Y')
            segments = list(port)
            if len(segments) != 1:
                raise RuntimeError(f'{instance.raw_path}: expected 1 output segment')
            _, segment = segments[0]
            wire_path = safe_get_wire_path(segment)
            if not is_valid_wire_path(wire_path):
                raise RuntimeError(f'{instance.raw_path}: invalid output wire')

            if instance is tail:
                output_wire = wire_path
            else:
                internal_wires.append(wire_path)

        if output_wire is None:
            raise RuntimeError('Could not determine chain output')

        return output_wire, internal_wires

    def extract_boundary(self, chain_instances: Sequence[Instance]) -> Tuple[ChainBoundary, int, bool]:
        """Extract boundary info. Returns (boundary, constant_count, is_degenerate)."""
        if not chain_instances:
            raise ValueError('Empty chain')

        chain_ids = {inst.raw_path for inst in chain_instances}
        output, internal_wires = self.collect_output_wires(chain_instances)

        internal_paths = {w.raw for w in internal_wires}
        internal_paths.add(output.raw)

        inputs, constant_count = self.collect_external_inputs(chain_instances, chain_ids, internal_paths)
        is_degenerate = len(inputs) < 2

        boundary = ChainBoundary(inputs=inputs, output=output, internal_wires=internal_wires)
        return boundary, constant_count, is_degenerate


def _remove_instance_safely(module: Module, inst: Instance) -> None:
    try:
        module.remove_instance(inst)
    except Exception:
        pass


def remove_instances(module: Module, instances: Sequence[Instance]) -> None:
    for inst in instances:
        _remove_instance_safely(module, inst)


def build_instance_lookup(module: Module) -> Dict[str, Any]:
    lookup: Dict[str, Any] = {}
    for key in module.instances.keys():
        key_str = str(key)
        lookup[key_str] = key
        lookup[key_str.split('.')[-1]] = key
    return lookup


def fuzzy_find_instance(module: Module, search: str) -> Optional[Any]:
    keys = list(module.instances.keys())
    matches = [k for k in keys if str(k).endswith(search)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        return min(matches, key=lambda x: len(str(x)))

    matches = [k for k in keys if search in str(k)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        return min(matches, key=lambda x: len(str(x)))
    return None


def resolve_chain_instances(module: Module, keys: Sequence[str]) -> List[Instance]:
    lookup = build_instance_lookup(module)
    resolved: List[Instance] = []

    for key in keys:
        key_str = str(key)
        short = key_str.split('.')[-1]
        prefixed = f'{module.name}.{key_str}'
        prefixed_short = f'{module.name}.{short}'

        inst_key = lookup.get(key_str) or lookup.get(short) or lookup.get(prefixed) or lookup.get(prefixed_short)
        if inst_key is None:
            inst_key = fuzzy_find_instance(module, key_str) or fuzzy_find_instance(module, short)
        if inst_key is None:
            raise KeyError(f'Could not resolve: {key_str}')

        resolved.append(module.instances[inst_key])

    return resolved


def _remove_instance_and_log(module: Module, inst_key: str, instance: Instance, const_output: str) -> bool:
    """Remove instance and log outcome."""
    try:
        module.remove_instance(instance)
    except Exception as e:
        LOG.debug(f'Could not remove {inst_key}: {e}')
        return False

    LOG.debug(f'Removed degenerate gate {inst_key} (output={const_output})')
    return True


def _gate_constant_output(cfg: GateConfig, has_one: bool, has_zero: bool) -> Optional[str]:
    gate_name = cfg.name.lower()
    if gate_name == 'or':
        return "1'b1" if has_one else "1'b0"
    if gate_name == 'and':
        return "1'b0" if has_zero else "1'b1"
    return None


def _analyze_gate_inputs(instance: Instance) -> Tuple[int, bool, bool]:
    """Return (real_inputs, has_one, has_zero)."""
    real_inputs = 0
    has_one = False
    has_zero = False

    for port_name in ('A', 'B'):
        port = instance.ports.get(port_name)
        if port is None:
            continue
        for _, segment in port:
            wire_path = safe_get_wire_path(segment)
            if is_constant_wire(wire_path):
                raw = getattr(wire_path, 'raw', '') if wire_path else ''
                if raw in ('1', "1'b1"):
                    has_one = True
                else:
                    has_zero = True
            elif is_valid_wire_path(wire_path):
                real_inputs += 1

    return real_inputs, has_one, has_zero


def _has_valid_single_output(instance: Instance) -> bool:
    """True if instance has Y with exactly one segment and valid wire."""
    output_port = instance.ports.get('Y')
    if output_port is None:
        return False

    output_segments = list(output_port)
    if len(output_segments) != 1:
        return False

    _, output_segment = output_segments[0]
    output_wire = safe_get_wire_path(output_segment)
    return is_valid_wire_path(output_wire)


def _collect_degenerate_gate_removal(
    inst_key: str,
    instance: Instance,
    cfg: GateConfig,
) -> Optional[Tuple[str, Instance, str]]:
    if instance.instance_type != cfg.nsubtype:
        return None

    real_inputs, has_one, has_zero = _analyze_gate_inputs(instance)
    if real_inputs > 0:
        return None

    const_output = _gate_constant_output(cfg, has_one=has_one, has_zero=has_zero)
    if const_output is None:
        return None

    if not _has_valid_single_output(instance):
        return None

    return inst_key, instance, const_output


def remove_degenerate_gates(module: Module, cfg: GateConfig) -> int:
    """Remove degenerate gates (only constant inputs) from a module."""
    removed_count = 0
    gates_to_remove: List[Tuple[str, Instance, str]] = []

    for inst_key, instance in list(module.instances.items()):
        item = _collect_degenerate_gate_removal(inst_key, instance, cfg)
        if item is not None:
            gates_to_remove.append(item)

    for inst_key, instance, const_output in gates_to_remove:
        if _remove_instance_and_log(module, inst_key, instance, const_output):
            removed_count += 1

    return removed_count


class ChainReplacer:
    """Resolves, validates, disconnects and replaces a chain with a balanced tree."""

    def __init__(self, boundary_extractor: ChainBoundaryExtractor) -> None:
        self.boundary_extractor = boundary_extractor

    def replace_chain(self, module: Module, chain_keys: Sequence[str], prefix: str, cfg: GateConfig) -> ChainInfo:
        info = ChainInfo(chain_keys=list(chain_keys), status=ChainStatus.REPLACED, num_gates=len(chain_keys))

        instances = self._resolve_instances(module, chain_keys, info, prefix)
        if instances is None:
            return info

        boundary = self._extract_boundary(instances, info, prefix)
        if boundary is None:
            return info

        if info.status == ChainStatus.SKIPPED_DEGENERATE:
            return info

        if not self._disconnect_instances(module, instances, info, prefix):
            return info

        self._build_tree(module, boundary, prefix, cfg, info)
        self._log_success(prefix, instances, boundary, info.num_constant_inputs)
        return info

    @staticmethod
    def _resolve_instances(
        module: Module,
        chain_keys: Sequence[str],
        info: ChainInfo,
        prefix: str,
    ) -> Optional[List[Instance]]:
        if not chain_keys:
            info.status = ChainStatus.SKIPPED_RESOLUTION_FAILED
            info.error_message = 'Empty chain'
            return None

        try:
            return resolve_chain_instances(module, chain_keys)
        except KeyError as e:
            info.status = ChainStatus.SKIPPED_RESOLUTION_FAILED
            info.error_message = str(e)
            LOG.info(f'Skipping {prefix}: {e}')
            return None

    def _extract_boundary(self, instances: List[Instance], info: ChainInfo, prefix: str) -> Optional[ChainBoundary]:
        try:
            boundary, const_count, is_degenerate = self.boundary_extractor.extract_boundary(instances)
            info.num_inputs = len(boundary.inputs)
            info.num_internal_wires = len(boundary.internal_wires)
            info.num_constant_inputs = const_count
            info.output_wire = boundary.output.raw
            info.input_wires = [w.raw for w in boundary.inputs]

            if is_degenerate:
                info.status = ChainStatus.SKIPPED_DEGENERATE
                info.error_message = f'Degenerate chain: {info.num_inputs} real inputs, {const_count} constants'
                LOG.debug(f'Skipping degenerate {prefix}: {info.num_inputs} inputs, {const_count} constants')
            return boundary
        except Exception as e:
            info.status = ChainStatus.SKIPPED_BOUNDARY_FAILED
            info.error_message = str(e)
            LOG.info(f'Skipping {prefix}: {e}')
            return None

    @staticmethod
    def _disconnect_instances(module: Module, instances: List[Instance], info: ChainInfo, prefix: str) -> bool:
        try:
            remove_instances(module, instances)
            return True
        except Exception as e:
            info.status = ChainStatus.SKIPPED_DISCONNECT_FAILED
            info.error_message = str(e)
            LOG.info(f'Skipping {prefix}: {e}')
            return False

    @staticmethod
    def _build_tree(module: Module, boundary: ChainBoundary, prefix: str, cfg: GateConfig, info: ChainInfo) -> None:
        try:
            GateTreeBuilder(module, prefix, boundary, cfg).build()
        except Exception as e:
            info.status = ChainStatus.FAILED_TREE_BUILD
            info.error_message = str(e)
            raise RuntimeError(f'Tree build failed: {e}') from e

    @staticmethod
    def _log_success(prefix: str, instances: List[Instance], boundary: ChainBoundary, const_count: int) -> None:
        const_msg = f' ({const_count} constants)' if const_count else ''
        LOG.info(f'{prefix}: {len(instances)} gates → tree ({len(boundary.inputs)} inputs){const_msg}')


class GateChainScanner:
    """Subprocess-based chain scanner."""

    def __init__(self, script_path: str, python: str | None = None) -> None:
        self.script_path = script_path
        self.python = python or sys.executable

    def scan_module(self, input_path: str, top: str, module: str, gate: str) -> List[List[str]]:
        cmd = [
            self.python,
            self.script_path,
            '--scan-module',
            module,
            '--input',
            input_path,
            '--top',
            top,
            '--gate',
            gate,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Scan failed for '{module}': {result.stderr}")
        return json.loads(result.stdout)

    def collect_chains(self, input_path: str, top: str, modules: List[str], gate: str) -> Dict[str, List[List[str]]]:
        chains: Dict[str, List[List[str]]] = {}

        LOG.info(f'Scanning {len(modules)} modules for {gate}-chains...')
        for i, name in enumerate(modules, 1):
            LOG.debug(f'[{i}/{len(modules)}] {name}')
            found = self.scan_module(input_path, top, name, gate)
            if found:
                chains[name] = found
                LOG.debug(f'  Found {len(found)} chain(s)')

        total = sum(len(c) for c in chains.values())
        LOG.info(f'Total: {total} chains in {len(chains)} modules')
        return chains


def invalidate_graph_cache(module: Module) -> None:
    if hasattr(module, '_graph'):
        module._graph = None


def fix_invalid_verilog(filepath: str) -> int:
    with open(filepath, 'r') as f:
        lines = f.readlines()

    valid_lines = [line for line in lines if not line.strip().startswith("assign 1'b")]
    removed = len(lines) - len(valid_lines)

    if removed > 0:
        with open(filepath, 'w') as f:
            f.writelines(valid_lines)

    return removed


class CircuitOptimizer:
    """Coordinates scan/replace across a circuit."""

    def __init__(self, scanner: GateChainScanner, replacer: ChainReplacer) -> None:
        self.scanner = scanner
        self.replacer = replacer

    def optimize(
        self,
        input_path: str,
        top_module: str,
        configs: List[GateConfig],
        *,
        output_path: Optional[str],
        skip_modules: Set[str],
        remove_degenerate: bool,
    ) -> CircuitOptimizationResult:
        result = CircuitOptimizationResult()

        circuit = nc_read(input_path, top=top_module)
        gate_names = ', '.join(cfg.name.upper() for cfg in configs)
        LOG.info_highlighted(f'{gate_names}-Chain Optimization: {circuit.name}')

        if remove_degenerate:
            self._phase0_remove_degenerate(circuit, configs)

        self._prepare_modules(circuit, configs)

        module_names = [name for name in circuit.modules.keys() if name not in skip_modules]
        all_chains_by_module = self._scan_all_chains(input_path, top_module, module_names, configs)

        self._update_detection_stats(result, circuit, all_chains_by_module)
        self._replace_all(result, circuit, all_chains_by_module)

        self._write_output_if_requested(circuit, output_path)

        result._log_report(LOG.info)
        return result

    @staticmethod
    def _phase0_remove_degenerate(circuit: Circuit, configs: List[GateConfig]) -> None:
        LOG.info('Phase 0: Removing degenerate gates (only constant inputs)...')
        total_removed = 0
        for mod in circuit:
            for cfg in configs:
                total_removed += remove_degenerate_gates(mod, cfg)
        LOG.info(f'Removed {total_removed} degenerate gates')

    @staticmethod
    def _prepare_modules(circuit: Circuit, configs: List[GateConfig]) -> None:
        for mod in circuit:
            mod.optimize()
            for cfg in configs:
                mod.split_all(cfg.nsubtype)
            invalidate_graph_cache(mod)

    def _scan_all_chains(
        self,
        input_path: str,
        top_module: str,
        module_names: List[str],
        configs: List[GateConfig],
    ) -> Dict[str, List[Tuple[GateConfig, List[List[str]]]]]:
        LOG.info('Phase 1: Scanning...')

        all_chains_by_module: Dict[str, List[Tuple[GateConfig, List[List[str]]]]] = defaultdict(list)

        for cfg in configs:
            LOG.info(f'  Scanning for {cfg.name.upper()} chains...')
            chains_by_module = self.scanner.collect_chains(input_path, top_module, module_names, cfg.name)

            for mod_name, chains in chains_by_module.items():
                all_chains_by_module[mod_name].append((cfg, chains))

            total = sum(len(c) for c in chains_by_module.values())
            LOG.info(f'    Found {total} {cfg.name.upper()} chains in {len(chains_by_module)} modules')

        return dict(all_chains_by_module)

    @staticmethod
    def _update_detection_stats(
        result: CircuitOptimizationResult,
        circuit: Circuit,
        all_chains_by_module: Dict[str, List[Tuple[GateConfig, List[List[str]]]]],
    ) -> None:
        result.modules_processed = len(circuit.modules)
        result.modules_with_chains = len(all_chains_by_module)
        result.total_chains_detected = sum(len(chains) for mod_chains in all_chains_by_module.values() for _, chains in mod_chains)

    def _replace_all(
        self,
        result: CircuitOptimizationResult,
        circuit: Circuit,
        all_chains_by_module: Dict[str, List[Tuple[GateConfig, List[List[str]]]]],
    ) -> None:
        LOG.info(f'Phase 2: Replacing {result.total_chains_detected} chains...')
        ts = int(time.time() * 1000)

        for mod_name, mod_chain_list in all_chains_by_module.items():
            mod = circuit.modules[mod_name]
            total_chains_in_mod = sum(len(chains) for _, chains in mod_chain_list)
            LOG.info(f'Module: {mod_name} ({total_chains_in_mod} chains)')

            for cfg, chains in mod_chain_list:
                self._replace_for_cfg(result, mod, mod_name, cfg, chains, ts)

            invalidate_graph_cache(mod)
            gc.collect()

    def _replace_for_cfg(
        self,
        result: CircuitOptimizationResult,
        mod: Module,
        mod_name: str,
        cfg: GateConfig,
        chains: List[List[str]],
        ts: int,
    ) -> None:
        analysis = analyze_module_gates(mod, cfg)
        report = ModuleReport(module_name=f'{mod_name}_{cfg.name}', gate_analysis=analysis, chains_detected=len(chains))
        mod_result = ReplacementResult(chains_detected=chains)

        for idx, keys in enumerate(chains, 1):
            prefix = f'{mod.name}_{cfg.chain_prefix}{idx}_{ts}'
            self._replace_one_chain(result, report, mod_result, mod, cfg, keys, prefix)

        key = f'{mod_name}_{cfg.name}'
        result.module_results[key] = mod_result
        result.module_reports[key] = report

    def _replace_one_chain(
        self,
        result: CircuitOptimizationResult,
        report: ModuleReport,
        mod_result: ReplacementResult,
        mod: Module,
        cfg: GateConfig,
        keys: List[str],
        prefix: str,
    ) -> None:
        try:
            info = self.replacer.replace_chain(mod, keys, prefix, cfg)
            mod_result.chain_details.append(info)
            self._apply_chain_outcome(result, report, mod_result, info)
        except Exception as e:
            err = str(e)
            info = ChainInfo(
                chain_keys=list(keys),
                status=ChainStatus.FAILED_TREE_BUILD,
                error_message=err,
                num_gates=len(keys),
            )
            mod_result.chain_details.append(info)

            mod_result.chains_failed += 1
            report.chains_failed += 1
            result.total_chains_failed += 1

            report.failed_details.append({'num_gates': len(keys), 'error': err, 'keys': list(keys)})
            LOG.error(f'{prefix}: {e}')

    @staticmethod
    def _apply_chain_outcome(
        result: CircuitOptimizationResult,
        report: ModuleReport,
        mod_result: ReplacementResult,
        info: ChainInfo,
    ) -> None:
        if info.was_replaced:
            mod_result.chains_replaced += 1
            report.chains_replaced += 1
            result.total_chains_replaced += 1
            return

        if info.was_skipped:
            mod_result.chains_skipped += 1
            report.chains_skipped += 1
            result.total_chains_skipped += 1
            report.skipped_details.append(
                {
                    'num_gates': info.num_gates,
                    'num_inputs': info.num_inputs,
                    'num_constants': info.num_constant_inputs,
                    'status': info.status.name,
                    'error': info.error_message,
                    'keys': info.chain_keys,
                }
            )
            return

        mod_result.chains_failed += 1
        report.chains_failed += 1
        result.total_chains_failed += 1

    @staticmethod
    def _write_output_if_requested(circuit: Circuit, output_path: Optional[str]) -> None:
        if not output_path:
            return
        circuit.write(output_path, overwrite=True)
        removed = fix_invalid_verilog(output_path)
        if removed > 0:
            LOG.warn(f'Removed {removed} invalid lines')


# Main Entry Point
def optimize_circuit(
    input_path: str,
    top_module: str,
    gates: Union[str, List[str]] = 'or',
    output_path: Optional[str] = None,
    skip_modules: Optional[Set[str]] = None,
    remove_degenerate: bool = False,
) -> CircuitOptimizationResult:
    """Optimize circuit by replacing gate chains with balanced trees."""
    gate_list = _normalize_gates(gates)
    configs = [get_gate_config(g) for g in gate_list]

    scanner = GateChainScanner(script_path=__file__)
    replacer = ChainReplacer(boundary_extractor=ChainBoundaryExtractor())
    optimizer = CircuitOptimizer(scanner=scanner, replacer=replacer)

    return optimizer.optimize(
        input_path=input_path,
        top_module=top_module,
        configs=configs,
        output_path=output_path,
        skip_modules=skip_modules or set(),
        remove_degenerate=remove_degenerate,
    )


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--scan-module', dest='module_name')
    parser.add_argument('--input', dest='input_path')
    parser.add_argument('--top', dest='top_module')
    parser.add_argument('--gate', dest='gate')
    args = parser.parse_args()

    if args.module_name:
        circuit = nc_read(args.input_path, top=args.top_module)
        cfg = get_gate_config(args.gate)

        module = circuit.modules.get(args.module_name)
        if module is None:
            print('[]')
        else:
            module.optimize()
            module.split_all(cfg.nsubtype)
            chains = find_gate_chains_netlist(module, cfg)
            print(json.dumps(chains))
