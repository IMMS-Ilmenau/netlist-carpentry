from typing import Dict, List, Union, overload

import networkx as nx

from netlist_carpentry.core.circuit import Circuit
from netlist_carpentry.core.graph.module_graph import ModuleGraph
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.utils.log import LOG

COMB_LOOP = List[str]
COMB_LOOPS = List[COMB_LOOP]


def has_comb_loops(module_or_circuit: Union[Module, Circuit]) -> bool:
    """Checks whether the given module or circuit contains combinational loops and prints a warning if found.

    Args:
        module_or_circuit (Union[Module, Circuit]): The module to check for combinational loops.
            Alternatively, a circuit object, where each module is checked for combinational loops.

    Returns:
        bool: True if at least one combinational loop was found, False otherwise.
    """
    if isinstance(module_or_circuit, Circuit):
        return any(has_comb_loops(m) for m in module_or_circuit)
    return module_has_comb_loops(module_or_circuit)


def module_has_comb_loops(module: Module) -> bool:
    """Checks whether the given module contains combinational loops and prints a warning if found.

    Args:
        module (Module): The module to check for combinational loops.

    Returns:
        bool: True if at least one combinational loop was found, False otherwise.
    """
    G_comb = combinational_subgraph(module)
    if not nx.is_directed_acyclic_graph(G_comb):
        LOG.warn(f'Detected combinational loops in module {module.name}!')
        return True
    return False


@overload
def find_comb_loops(module_or_circuit: Module) -> COMB_LOOPS: ...
@overload
def find_comb_loops(module_or_circuit: Circuit) -> Dict[str, COMB_LOOPS]: ...
def find_comb_loops(module_or_circuit: Union[Module, Circuit]) -> Union[Dict[str, COMB_LOOPS], COMB_LOOPS]:
    """Returns all combinational loops of this module.

    In case the actual loops or the amound of loops does not matter, use the function `has_comb_loops` instead.
    The function `has_comb_loops` is faster (especially for very large modules) as it only checks if the graph
    is acyclic and does not bother to find all loops.

    Args:
        module_or_circuit (Union[Module, Circuit]): The module to return all combinational loops from.
            Alternatively, a circuit object, where each module is checked for combinational loops.

    Returns:
        Union[Dict[str, COMB_LOOPS], COMB_LOOPS]: A list of combinational loops, where each loop again is a list,
            containing the node names that form the combinational loop, ordered by occurence in the loop.
            This means, the last element in the list drives the first element.
            If this list is empty, no combinational loops were found.
            If a circuit is provided, returns a dictionary with module names as keys and lists of combinational loops as values.
    """
    if isinstance(module_or_circuit, Circuit):
        return {module.name: find_comb_loops(module) for module in module_or_circuit}
    return module_find_comb_loops(module_or_circuit)


def module_find_comb_loops(module: Module) -> COMB_LOOPS:
    """Returns all combinational loops of this module.

    In case the actual loops or the amound of loops does not matter, use the function `has_comb_loops` instead.
    The function `has_comb_loops` is faster (especially for very large modules) as it only checks if the graph
    is acyclic and does not bother to find all loops.

    Args:
        module (Module): The module to return all combinational loops from.

    Returns:
        COMB_LOOPS: A list of combinational loops, where each loop again is a list,
            containing the node names that form the combinational loop, ordered by occurence in the loop.
            This means, the last element in the list drives the first element.
            If this list is empty, no combinational loops were found.
    """
    G_comb = combinational_subgraph(module)
    return list(nx.simple_cycles(G_comb))


def combinational_subgraph(module: Module) -> ModuleGraph:
    """Returns a subgraph of the given module's graph that only contains combinational elements (and submodule instances).

    Args:
        module (Module): The module to get the combinational subgraph from.

    Returns:
        ModuleGraph: A subgraph that only contains combinational elements (and possibly submodule instances).
    """
    G = module.graph()
    comb_nodes = []
    for node in G.nodes():
        if G.nodes[node]['ntype'] == 'INSTANCE' and module.instances[node].is_primitive:  # type: ignore[misc]
            inst = module.instances[node]
            if getattr(inst, 'is_sequential', False):  # type: ignore[misc]
                continue
        comb_nodes.append(node)

    return ModuleGraph(G.subgraph(comb_nodes))
