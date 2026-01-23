"""Module for constraints that need to be satisfied by a possible matching subgraph."""

from __future__ import annotations

from netlist_carpentry.core.graph.module_graph import ModuleGraph


class Constraint:
    """This class represents a constraint that needs to be satisfied by a matching subgraph."""

    def check(self, potential_match_graph: ModuleGraph, circuit_graph: ModuleGraph) -> bool:
        raise NotImplementedError('Check method not implemented for base class!')


class CascadingGateConstraint(Constraint):
    """This constraint checks if a potentially matching subgraph forms a cascading gate structure."""

    def __init__(self, instance_type: str):
        self.instance_type = instance_type

    def check(self, potential_match_graph: ModuleGraph, circuit_graph: ModuleGraph) -> bool:
        for n in potential_match_graph.nodes:
            if list(potential_match_graph.predecessors(n)):  # Not the first node of the pattern (this node can have driving gates)
                pred = list(circuit_graph.predecessors(n))
                # For a cascading sequence of gates, the predecessor nodes must not be gates of the same type
                # E.q. if the inputs of an OR gate are driven by two OR gates, this is already a tree and not a cascading sequence
                if all(circuit_graph.node_subtype(pn) == self.instance_type for pn in pred):
                    return False
        return True


CASCADING_OR_CONSTRAINT = CascadingGateConstraint('§or')
CASCADING_AND_CONSTRAINT = CascadingGateConstraint('§and')
