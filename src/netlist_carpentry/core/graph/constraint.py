from __future__ import annotations

from networkx import MultiDiGraph as MDG


class Constraint:
    """This class represents a constraint that needs to be satisfied by a matching subgraph."""

    def check(self, potential_match_graph: MDG[str], circuit_graph: MDG[str]) -> bool:
        raise NotImplementedError('Check method not implemented for base class!')


class CascadingGateConstraint(Constraint):
    """This constraint checks if a potentially matching subgraph forms a cascading gate structure."""

    def __init__(self, instance_type: str):
        self.instance_type = instance_type

    def check(self, potential_match_graph: MDG[str], circuit_graph: MDG[str]) -> bool:
        for n in potential_match_graph.nodes:
            if list(potential_match_graph.predecessors(n)):  # Not the first node of the pattern (this node can have driving gates)
                pred = list(circuit_graph.predecessors(n))
                # For a cascading sequence of gates, the predecessor nodes must not be gates of the same type
                # E.q. if the inputs of an OR gate are driven by two OR gates, this is already a tree and not a cascading sequence
                if all(circuit_graph.nodes[pn]['ntype_info'] == self.instance_type for pn in pred):
                    return False
        return True


CASCADING_OR_CONSTRAINT = CascadingGateConstraint('§or')
CASCADING_AND_CONSTRAINT = CascadingGateConstraint('§and')
