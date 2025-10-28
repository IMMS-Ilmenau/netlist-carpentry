from typing import Dict, Set, Union

from netlist_carpentry import LOG
from netlist_carpentry.core.exceptions import EvaluationError
from netlist_carpentry.core.netlist_elements.element_path import InstancePath, PortPath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.mixins.module_base import ModuleBaseMixin
from netlist_carpentry.core.netlist_elements.port import Port
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.core.protocols.netlist_elements import ModuleLike, PortSegmentLike


class EvaluationMixin(ModuleBaseMixin):
    @property
    def instances_with_constant_inputs(self) -> Set[Instance]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this property.')

    @property
    def input_ports(self) -> Set[Port]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this property.')

    def get_outgoing_edges(self, instance_name: str) -> Dict[str, Dict[int, WireSegment]]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this method.')

    def get_load_ports(self, ws_path: WireSegmentPath) -> Set[PortSegmentLike]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this method.')

    def evaluate(self, modules: Dict[str, ModuleLike] = {}) -> None:
        try:
            self._evaluate_breadth_first(modules)
        except Exception as e:
            raise EvaluationError(f'Unable to evaluate module {self.name}, encountered exception:\n{type(e).__name__}: {e}!')

    def _evaluate_breadth_first(self, modules: Dict[str, ModuleLike] = {}) -> None:
        """
        Performs the breadth-first evaluation of the module.

        This method evaluates the module in a breadth-first manner, starting from the input ports.
        It uses a queue to keep track of the elements that need to be evaluated next.
        The evaluation process involves evaluating each element (either an instance or a wire segment) and adding its
        successors to the queue. The process continues until all elements have been evaluated.

        This method is needed for the overall evaluation of the module, as it ensures that all elements are properly
        evaluated in the correct hierarchical order.
        However, wires or instances on the same hierarchical level are evaluated in random order.
        """
        wire_segments: Set[WireSegment] = set()
        nodes: Set[Union[Instance, Port]] = set()
        nodes.update(self.instances_with_constant_inputs)
        for p in self.input_ports:
            wire_segments.update({self.get_from_path(path) for path in p.connected_wire_segments if self.get_from_path(path) is not None})
        while wire_segments:
            # Evaluate wire segments and collect instances to evaluate next
            for wseg in wire_segments:
                nodes.update(self._evaluate_ws(wseg.path))
            wire_segments = set()
            # Evaluate instances and collect wire segments to evaluate next
            for node in nodes:
                wire_segments.update(self._evaluate_instance_wrapper(node.path, modules))
            nodes = set()

    def _evaluate_ws(self, ws_path: WireSegmentPath) -> Set[Union[Instance, Port]]:
        wseg = self.get_from_path(ws_path)
        if wseg is not None:
            wseg.evaluate()
            next_eval: Set[Union[Instance, Port]] = set()
            for ps in self.get_load_ports(wseg.path):
                inst = ps.parent_parent_name
                port = ps.parent_name
                next_eval.add(self.instances[inst] if inst in self.instances else self.ports[port])
            return next_eval
        LOG.debug(f'Path {ws_path.raw} is not a valid wire segment path (type {ws_path.type}), skipping evaluation in this branch!')
        return set()

    def _evaluate_instance_wrapper(self, instance_path: Union[InstancePath, PortPath], modules: Dict[str, ModuleLike] = {}) -> Set[WireSegment]:
        inst = self.get_from_path(instance_path)
        if inst is not None and isinstance(inst, Instance):
            self._evaluate_instance(inst, modules)
            next_edges = set()
            for w_dict in self.get_outgoing_edges(inst.name).values():
                for ws in w_dict.values():
                    next_edges.add(ws)
            return next_edges
        LOG.debug(f'Path {instance_path.raw} is not a valid instance path (type {instance_path.type}), skipping evaluation in this branch!')
        return set()

    def _evaluate_instance(self, instance: Instance, modules: Dict[str, ModuleLike]) -> None:
        try:
            instance.evaluate()
        except NotImplementedError:
            m = modules[instance.instance_type]
            for p in instance.input_ports:
                for seg_idx in p.segments:
                    m.ports[p.name][seg_idx].set_signal(p[seg_idx].signal)
            m.evaluate(modules)
            for p in m.output_ports:
                for seg_idx in p.segments:
                    instance.ports[p.name][seg_idx].set_signal(p[seg_idx].signal)
