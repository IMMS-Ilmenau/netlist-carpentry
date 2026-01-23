"""Mixin for signal evaluation of a module."""

from typing import TYPE_CHECKING, Dict, List, Union

from netlist_carpentry import LOG, Instance, Port
from netlist_carpentry.core.exceptions import EvaluationError
from netlist_carpentry.core.netlist_elements.element_path import InstancePath, PortPath, WireSegmentPath
from netlist_carpentry.core.netlist_elements.mixins.module_base import ModuleBaseMixin
from netlist_carpentry.core.netlist_elements.port_segment import PortSegment
from netlist_carpentry.core.netlist_elements.wire_segment import WireSegment
from netlist_carpentry.utils.custom_list import CustomList

if TYPE_CHECKING:
    from netlist_carpentry import Module


class EvaluationMixin(ModuleBaseMixin):
    def get_outgoing_edges(self, instance_name: str) -> Dict[str, Dict[int, WireSegment]]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this method.')

    def get_load_ports(self, ws_path: WireSegmentPath) -> List[PortSegment]:
        raise NotImplementedError(f'Not implemented for mixin {self.__class__.__name__}. Any class using this mixin must implement this method.')

    def evaluate(self) -> None:
        """
        Performs the breadth-first evaluation of the module.

        This method evaluates the module in a breadth-first manner, starting from the input ports.
        It uses a queue to keep track of the elements that need to be evaluated next.
        The evaluation process involves evaluating each element (either an instance or a wire segment) and adding its
        successors to the queue. The process continues until all elements have been evaluated.

        This method is needed for the overall evaluation of the module, as it ensures that all elements are properly
        evaluated in the correct hierarchical order.
        """
        try:
            self._evaluate_breadth_first()
        except Exception as e:
            raise EvaluationError(f'Unable to evaluate module {self.name}, encountered exception:\n{type(e).__name__}: {e}!')

    def _evaluate_breadth_first(self) -> None:
        wire_segments: CustomList[WireSegment] = CustomList()
        nodes: CustomList[Union[Instance, Port['Module']]] = CustomList()
        nodes.extend(self.instances_with_constant_inputs)
        for p in self.input_ports:
            wire_segments.extend(
                [self.get_from_path(path) for path in p.connected_wire_segments.values() if self.get_from_path(path) is not None],
                skip_duplicates=True,
            )
        while wire_segments:
            # Evaluate wire segments and collect instances to evaluate next
            for wseg in wire_segments:
                nodes.extend(self._evaluate_ws(wseg.path), skip_duplicates=True)
            wire_segments = CustomList()
            # Evaluate instances and collect wire segments to evaluate next
            for node in nodes:
                wire_segments.extend(self._evaluate_instance_wrapper(node.path), skip_duplicates=True)
            nodes = CustomList()

    def _evaluate_ws(self, ws_path: WireSegmentPath) -> List[Union[Instance, Port['Module']]]:
        wseg = self.get_from_path(ws_path)
        wseg.evaluate()
        next_eval: CustomList[Union[Instance, Port['Module']]] = CustomList()
        for ps in self.get_load_ports(wseg.path):
            inst = ps.grandparent_name
            port = ps.parent_name
            next_eval.add(self.instances[inst] if inst in self.instances else self.ports[port])
        return next_eval

    def _evaluate_instance_wrapper(self, instance_path: Union[InstancePath, PortPath]) -> List[WireSegment]:
        inst = self.get_from_path(instance_path)
        if inst is not None and isinstance(inst, Instance):
            self._evaluate_instance(inst)
            next_edges: CustomList[WireSegment] = CustomList()
            for w_dict in self.get_outgoing_edges(inst.name).values():
                for ws in w_dict.values():
                    next_edges.add(ws)
            return next_edges
        LOG.debug(f'Path {instance_path.raw} is not a valid instance path (type {instance_path.type}), skipping evaluation in this branch!')
        return CustomList()

    def _evaluate_instance(self, instance: Instance) -> None:
        try:
            instance.evaluate()
        except NotImplementedError:
            m = self.circuit.modules[instance.instance_type]
            for pi in instance.input_ports:
                for seg_idx in pi.segments:
                    m.ports[pi.name][seg_idx].set_signal(pi[seg_idx].signal)
            m.evaluate()
            for po in m.output_ports:
                for seg_idx in po.segments:
                    instance.ports[po.name][seg_idx].set_signal(po[seg_idx].signal)
